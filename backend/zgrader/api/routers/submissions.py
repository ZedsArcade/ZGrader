import datetime
import io
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from zgrader.analysis import preprocessing, recompute
from zgrader.api.deps import get_current_user, require_operator
from zgrader.config import config
from zgrader.db import get_db
from zgrader.email.notifications import send_report_published, send_submission_received
from zgrader.models import (
    AuditLog,
    Card,
    ReportStatus,
    ScanImage,
    ScanSide,
    Settings,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from zgrader.reports import builder
from zgrader.scan_ingest import read_scan_metadata, sha256_file
from zgrader.schemas.admin import AutoPublishUpdate
from zgrader.schemas.submission import (
    CropPointsIn,
    RegionToggleIn,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionSummary,
)
from zgrader.worker.watcher import _IMAGE_SUFFIXES, _advance_submission, _confirmed_sides, process_submission_folder

router = APIRouter(prefix="/submissions", tags=["submissions"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_UPLOADABLE_STATUSES = (
    SubmissionStatus.created,
    SubmissionStatus.awaiting_scans,
    SubmissionStatus.draft_ready,
)
_PIL_FORMAT_TO_SUFFIX = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "TIFF": ".tiff",
}
_REGION_ID_RE = re.compile(r"^[a-z0-9_]+$")
_REGION_KEY_RE = re.compile(r"^(front|back):(centering|corners|edges|surface):[a-z0-9_]+$")
_SUFFIX_TO_MEDIA_TYPE = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".tiff": "image/tiff", ".tif": "image/tiff"}


def _next_submission_code(db: Session) -> str:
    count = db.query(Submission).count()
    return f"SUB-{count + 1:05d}"


def _get_owned_submission(code: str, user: User, db: Session) -> Submission:
    submission = db.query(Submission).filter(Submission.submission_code == code).first()
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    if user.role != UserRole.operator and submission.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your submission")
    return submission


@router.post("", response_model=SubmissionDetail, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Submission:
    code = _next_submission_code(db)
    submission = Submission(
        submission_code=code,
        user_id=user.id,
        status=SubmissionStatus.created,
        language=payload.language,
    )
    db.add(submission)
    db.flush()

    db.add(
        Card(
            submission_id=submission.id,
            game=payload.game,
            card_name=payload.card_name,
            set_name=payload.set_name,
            card_number=payload.card_number,
            foil=payload.foil,
        )
    )

    # The operator scans into this folder; the watcher matches on its name.
    (Path(config.scans_dir) / code).mkdir(parents=True, exist_ok=True)

    db.commit()
    db.refresh(submission)

    settings = db.query(Settings).first()
    send_submission_received(user, submission, settings)

    return submission


@router.get("", response_model=list[SubmissionSummary])
def list_submissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Submission]:
    query = db.query(Submission)
    if user.role != UserRole.operator:
        query = query.filter(Submission.user_id == user.id)
    return query.order_by(Submission.created_at.desc()).all()


@router.get("/{code}", response_model=SubmissionDetail)
def get_submission(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Submission:
    return _get_owned_submission(code, user, db)


@router.post("/{code}/scans", response_model=SubmissionDetail)
async def upload_scan(
    code: str,
    side: Literal["front", "back"] = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Self-serve counterpart to the operator manual-drop workflow: writes
    the uploaded image into the same scans_dir/<code>/ folder the watcher
    already watches, using the same front.<ext>/back.<ext> naming it already
    matches on, and registers a ScanImage row. Unlike the operator flatbed
    path, this does NOT auto-confirm the crop or trigger analysis -- a
    self-serve photo is inconsistent, untrusted input (handheld angle,
    cluttered background), so the client must walk the user through the
    crop-adjust UI (GET .../suggest-crop, then POST .../confirm-crop) before
    analysis runs."""
    submission = _get_owned_submission(code, user, db)

    if submission.status not in _UPLOADABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Submission is '{submission.status.value}' -- scans can no longer be added",
        )
    if side in submission.scan_sides:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {side} scan has already been uploaded")

    content = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large")

    try:
        image = Image.open(io.BytesIO(content))
        image_format = image.format
        image.verify()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a valid image") from None

    suffix = _PIL_FORMAT_TO_SUFFIX.get(image_format or "")
    if suffix is None or suffix not in _IMAGE_SUFFIXES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported image format -- use JPEG, PNG, or TIFF")

    folder = Path(config.scans_dir) / code
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / f"{side}{suffix}"
    file_path.write_bytes(content)

    width, height, dpi = read_scan_metadata(file_path)
    db.add(
        ScanImage(
            submission_id=submission.id,
            side=ScanSide(side),
            file_path=str(file_path),
            original_filename=file.filename or file_path.name,
            dpi=dpi,
            width_px=width,
            height_px=height,
            checksum=sha256_file(file_path),
        )
    )
    db.commit()
    db.refresh(submission)
    return submission


def _get_scan(submission: Submission, side: str) -> ScanImage:
    scan = next((s for s in submission.scan_images if s.side.value == side), None)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {side} scan uploaded yet")
    return scan


@router.get("/{code}/scans/{side}/raw")
def get_side_raw(
    code: str,
    side: Literal["front", "back"],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """The just-uploaded, not-yet-analyzed scan file, for the crop-adjust
    UI to display before a crop is confirmed -- unlike /photo (which serves
    the post-analysis deskewed base image and 404s until analysis runs)."""
    submission = _get_owned_submission(code, user, db)
    scan = _get_scan(submission, side)
    media_type = _SUFFIX_TO_MEDIA_TYPE.get(Path(scan.file_path).suffix.lower(), "application/octet-stream")
    return FileResponse(scan.file_path, media_type=media_type)


@router.get("/{code}/scans/{side}/suggest-crop")
def suggest_crop(
    code: str,
    side: Literal["front", "back"],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """A starting suggestion for the manual crop-adjust UI: auto-detects
    the card boundary in the raw upload and returns its 4 corner points
    (raw pixel space) plus the image's own dimensions for normalization.
    Never persists anything -- safe to call repeatedly. On detection
    failure, falls back to the raw image's own 4 corners so the user still
    has draggable handles to start from."""
    submission = _get_owned_submission(code, user, db)
    scan = _get_scan(submission, side)
    try:
        image = preprocessing.load_image(scan.file_path)
        box, _info = preprocessing.detect_boundary(image)
        points = box.tolist()
    except Exception:
        points = [[0, 0], [scan.width_px, 0], [scan.width_px, scan.height_px], [0, scan.height_px]]
    return {"points": points, "width_px": scan.width_px, "height_px": scan.height_px}


def _validate_points(payload: CropPointsIn, scan: ScanImage) -> None:
    if len(payload.points) != 4:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Exactly 4 points are required")
    for x, y in payload.points:
        if not (0 <= x <= scan.width_px and 0 <= y <= scan.height_px):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Points must be within the image bounds")


@router.post("/{code}/scans/{side}/snap-crop")
def snap_crop(
    code: str,
    side: Literal["front", "back"],
    payload: CropPointsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Refine the user's current 4 crop corners toward the auto-detected
    card boundary (each snaps only when it's already close), so an imperfect
    manual placement gets cleaned up. Returns the snapped points in raw
    pixel space; never persists -- the client updates its handles and the
    user still confirms via confirm-crop."""
    submission = _get_owned_submission(code, user, db)
    scan = _get_scan(submission, side)
    _validate_points(payload, scan)
    image = preprocessing.load_image(scan.file_path)
    points = preprocessing.snap_points_to_boundary(image, [list(p) for p in payload.points])
    return {"points": points}


@router.post("/{code}/scans/{side}/confirm-crop", response_model=SubmissionDetail)
def confirm_crop(
    code: str,
    side: Literal["front", "back"],
    payload: CropPointsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Persists the user-confirmed (or accepted-as-suggested) 4 crop points
    for one side and advances the submission's processing state machine --
    the self-serve counterpart to the operator flatbed path's automatic
    boundary detection at registration time."""
    submission = _get_owned_submission(code, user, db)
    if submission.status not in _UPLOADABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Submission is '{submission.status.value}' -- crop can no longer be confirmed",
        )
    scan = _get_scan(submission, side)
    _validate_points(payload, scan)

    scan.crop_points = [list(point) for point in payload.points]
    db.commit()
    db.refresh(submission)

    confirmed = _confirmed_sides(submission)
    submission = _advance_submission(db, submission, confirmed, {ScanSide(side)}, code)
    db.refresh(submission)
    return submission


@router.post("/{code}/regions/toggle", response_model=SubmissionDetail)
def toggle_region(
    code: str,
    payload: RegionToggleIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Dismiss (or restore) a single auto-detected finding the client
    believes is mistaken, then recompute the whole assessment (category
    scores + company comparisons) ignoring the dismissed findings. The
    dismissal flows into the published report, which is clearly marked
    client-adjusted -- see zgrader.reports.builder."""
    submission = _get_owned_submission(code, user, db)
    if submission.status != SubmissionStatus.draft_ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Submission is '{submission.status.value}' -- findings can only be adjusted while the draft is under review",
        )
    if not _REGION_KEY_RE.match(payload.region_key):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region key")

    current = list(submission.dismissed_regions or [])
    if payload.dismissed:
        if payload.region_key not in current:
            current.append(payload.region_key)
    else:
        current = [k for k in current if k != payload.region_key]
    submission.dismissed_regions = current

    db.add(
        AuditLog(
            submission_id=submission.id,
            user_id=user.id,
            action="region_dismissed" if payload.dismissed else "region_restored",
            detail={"region_key": payload.region_key},
        )
    )
    db.flush()
    recompute.recompute_submission(db, submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/{code}/scans/{side}/photo")
def get_side_photo(
    code: str,
    side: Literal["front", "back"],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """The plain analyzed photo for one side, for the web results page's
    annotated-photo display -- saved once per side in
    pipeline.py::_persist_side. 404 until analysis has actually run."""
    _get_owned_submission(code, user, db)
    photo_path = Path(config.reports_dir) / code / f"{side}_base.png"
    if not photo_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not available yet")
    return FileResponse(photo_path, media_type="image/png")


@router.get("/{code}/scans/{side}/regions/{category}/{region_id}/crop")
def get_region_crop(
    code: str,
    side: Literal["front", "back"],
    category: Literal["centering", "corners", "edges", "surface"],
    region_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """A single flagged region's zoomed breakout crop -- see
    zgrader.analysis.regions.build_regions for how region_id is derived and
    zgrader.analysis.annotate.crop_region for how the file is generated.
    Filenames are fully deterministic from (code, side, category,
    region_id), so this never needs a DB round-trip -- region_id is
    regex-validated before touching disk as defense in depth."""
    _get_owned_submission(code, user, db)
    if not _REGION_ID_RE.match(region_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Region not found")
    crop_path = Path(config.reports_dir) / code / f"{side}_{category}_{region_id}_crop.png"
    if not crop_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Region crop not available")
    return FileResponse(crop_path, media_type="image/png")


@router.get("/{code}/report")
def download_report(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    submission = _get_owned_submission(code, user, db)
    reports = sorted(submission.reports, key=lambda r: r.version, reverse=True)
    if not reports:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report generated yet")

    report = reports[0]
    if user.role != UserRole.operator and report.status != ReportStatus.published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not yet published")

    return FileResponse(report.pdf_path, media_type="application/pdf", filename=f"{code}.pdf")


@router.post("/{code}/approve", response_model=SubmissionDetail)
def approve_submission(
    code: str, operator: User = Depends(require_operator), db: Session = Depends(get_db)
) -> Submission:
    """Human review gate: an operator reviewing a draft_ready submission
    approves and publishes it in one action -- there's no useful
    intermediate "approved but not published" state for a single-operator
    business, so this mirrors the watcher's auto-publish path."""
    submission = db.query(Submission).filter(Submission.submission_code == code).first()
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    if submission.status not in (SubmissionStatus.draft_ready, SubmissionStatus.published):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Submission is '{submission.status.value}', not ready to approve",
        )
    if submission.status == SubmissionStatus.published:
        return submission  # idempotent

    report = builder.generate_report(db, submission)
    now = datetime.datetime.now(datetime.timezone.utc)
    report.status = ReportStatus.published
    report.approved_by_user_id = operator.id
    report.approved_at = now
    report.published_at = now
    submission.status = SubmissionStatus.published
    db.add(
        AuditLog(
            submission_id=submission.id,
            user_id=operator.id,
            action="approved_and_published",
            detail={"report_version": report.version},
        )
    )
    db.commit()
    db.refresh(submission)

    settings = db.query(Settings).first()
    send_report_published(submission.user, submission, settings)

    return submission


@router.patch("/{code}/auto-publish", response_model=SubmissionDetail)
def set_auto_publish_override(
    code: str,
    payload: AutoPublishUpdate,
    operator: User = Depends(require_operator),
    db: Session = Depends(get_db),
) -> Submission:
    submission = db.query(Submission).filter(Submission.submission_code == code).first()
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    submission.auto_publish = payload.auto_publish
    db.add(
        AuditLog(
            submission_id=submission.id,
            user_id=operator.id,
            action="auto_publish_override_changed",
            detail={"auto_publish": payload.auto_publish},
        )
    )
    db.commit()
    db.refresh(submission)
    return submission
