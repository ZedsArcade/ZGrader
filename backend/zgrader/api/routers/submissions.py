import datetime
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, selectinload

from zgrader import entitlements, images, sharing
from zgrader.analysis import artifacts, assessment, centering, pipeline, preprocessing, recompute, scale, scoring
from zgrader.api import capacity
from zgrader.api.deps import get_current_user, require_operator, require_verified_user
from zgrader.api.ratelimit import rate_limit
from zgrader.config import config
from zgrader.db import get_db
from zgrader.email.notifications import send_report_published, send_submission_received
from zgrader.models.settings import get_or_create_settings
from zgrader.models.submission import PRE_ANALYSIS_STATUSES, submission_code_seq
from zgrader.models import (
    AnalysisCategory,
    AnalysisSide,
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
from zgrader.storage import purge_submission_files
from zgrader.schemas.admin import AutoPublishUpdate
from zgrader.schemas.public_report import ShareStateOut
from zgrader.schemas.submission import (
    CardUpdate,
    CenteringAdjustIn,
    CropCheckOut,
    CropPointsIn,
    QuotaOut,
    RegionToggleIn,
    SubmissionCreate,
    SubmissionDetail,
    SubmissionSummary,
)
from zgrader.worker.watcher import _IMAGE_SUFFIXES, _advance_submission, _confirmed_sides, process_submission_folder

router = APIRouter(prefix="/submissions", tags=["submissions"])

_UPLOADABLE_STATUSES = (
    SubmissionStatus.created,
    SubmissionStatus.awaiting_scans,
    SubmissionStatus.draft_ready,
)
_REGION_ID_RE = re.compile(r"^[a-z0-9_]+$")

# Per-IP ceilings on the authenticated surface. Deliberately generous -- these
# are not guessing targets like login, and the quota already bounds how much
# real work an account can ask for. They exist so a runaway client or a
# credentialled scraper meets a wall well before the box does.
#
# The crop helpers share one bucket and get the loosest limit of the three:
# they fire repeatedly while somebody drags the crop handles, so a tight cap
# would make the adjuster feel broken rather than protect anything. They are
# also much cheaper than a full analysis -- boundary detection or a single
# geometry fit, not the whole pipeline -- which is why they are rate limited
# rather than held behind the capacity semaphore.
_submission_create_limit = rate_limit("submission_create", limit=30, window_seconds=3600)
_scan_upload_limit = rate_limit("scan_upload", limit=60, window_seconds=3600)
_confirm_crop_limit = rate_limit("confirm_crop", limit=30, window_seconds=3600)
_crop_helper_limit = rate_limit("crop_helpers", limit=120, window_seconds=3600)
_submission_read_limit = rate_limit("submission_read", limit=300, window_seconds=300)
_submission_delete_limit = rate_limit("submission_delete", limit=30, window_seconds=3600)

# The image/report/share/finding-adjustment/operator-publish surface: none of
# these existed as guessing targets, so none of them had a limiter at all --
# the gap an audit found alongside change-password's missing one. Grouped by
# cost, same reasoning as the block above: image bytes served on every page
# view get the loosest limit, a full PDF render the tightest, and the rest
# sit in between.
_submission_image_limit = rate_limit("submission_image", limit=120, window_seconds=60)
_report_download_limit = rate_limit("report_download", limit=20, window_seconds=900)
_share_manage_limit = rate_limit("share_manage", limit=30, window_seconds=900)
_submission_adjust_limit = rate_limit("submission_adjust", limit=60, window_seconds=300)
_card_update_limit = rate_limit("card_update", limit=60, window_seconds=3600)
_operator_publish_limit = rate_limit("operator_publish", limit=60, window_seconds=300)
_REGION_KEY_RE = re.compile(r"^(front|back):(centering|corners|edges|surface):[a-z0-9_]+$")
_SUFFIX_TO_MEDIA_TYPE = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".tiff": "image/tiff", ".tif": "image/tiff"}


def _next_submission_code(db: Session) -> str:
    """The next code, from a sequence that never issues one twice.

    This was `COUNT(*) + 1`, which reused a code as soon as any submission was
    deleted. See models.submission.submission_code_seq for what that cost --
    briefly, the code names the on-disk scans and reports directories, and
    those survive a database delete, so a reused code puts one customer's
    submission into another's folder.

    Deliberately not padded beyond five digits: SUB-100000 sorts after
    SUB-99999 lexically as well as numerically, so nothing downstream breaks
    when the count passes six figures.
    """
    number = db.execute(submission_code_seq.next_value().select()).scalar_one()
    return f"SUB-{number:05d}"


def _get_owned_submission(code: str, user: User, db: Session) -> Submission:
    submission = db.query(Submission).filter(Submission.submission_code == code).first()
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    if user.role != UserRole.operator and submission.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your submission")
    return submission


def _quota_exhausted(quota: entitlements.Quota) -> HTTPException:
    return HTTPException(
        status.HTTP_402_PAYMENT_REQUIRED,
        {
            "message": (
                "You've used all your checks for this period. They reset automatically, "
                "or a subscription removes the limit."
            ),
            "limit": quota.limit,
            "used": quota.used,
            "resets_at": quota.resets_at.isoformat() if quota.resets_at else None,
        },
    )


@router.get("/quota", response_model=QuotaOut, dependencies=[Depends(_submission_read_limit)])
def get_quota(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> QuotaOut:
    """The signed-in account's remaining checks and reset time.

    Declared before /{code} so the literal path isn't captured by that route's
    parameter -- FastAPI matches in declaration order.

    Reading rolls a lapsed window forward (see entitlements.get_quota), which
    mutates the user row, so this commits rather than leaving the reset to be
    re-derived on every subsequent read.
    """
    quota = entitlements.get_quota(db, user)
    db.commit()
    return QuotaOut(
        plan=quota.plan,
        unlimited=quota.unlimited,
        limit=quota.limit,
        used=quota.used,
        remaining=quota.remaining,
        period_days=quota.period_days,
        resets_at=quota.resets_at,
    )


@router.post(
    "",
    response_model=SubmissionDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_submission_create_limit)],
)
def create_submission(
    payload: SubmissionCreate,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> Submission:
    # Checked before anything is created, so a refused submission leaves no
    # row, no folder and no half-state behind. Nothing is spent here: a check
    # is charged when an analysis first scores the card (see
    # entitlements.charge_if_scored), so an abandoned draft costs nothing.
    quota = entitlements.get_quota(db, user)
    if not quota.can_submit:
        raise _quota_exhausted(quota)

    # Drafts are free until analysis scores them, so they need a ceiling of
    # their own. Mail-in submissions are waiting on the post, not on the
    # customer, and operators create on others' behalf.
    if not payload.mail_in and user.role != UserRole.operator:
        open_drafts = (
            db.query(Submission)
            .filter(
                Submission.user_id == user.id,
                Submission.mail_in.is_(False),
                Submission.charged_at.is_(None),
                Submission.status.in_(PRE_ANALYSIS_STATUSES),
            )
            .count()
        )
        if open_drafts >= config.max_open_drafts:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                {
                    "message": (
                        f"You have {open_drafts} unfinished checks. "
                        "Finish or delete one to start another."
                    ),
                    "code": "too_many_drafts",
                },
            )

    code = _next_submission_code(db)
    submission = Submission(
        submission_code=code,
        user_id=user.id,
        status=SubmissionStatus.created,
        language=payload.language,
        mail_in=payload.mail_in,
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

    # Only a mail-in is a submission the customer is waiting on us for; the
    # email carries the reference to put in the package. A photo draft is
    # created silently by its first upload and may never be finished.
    if submission.mail_in:
        settings = db.query(Settings).first()
        send_submission_received(user, submission, settings)

    return submission


def _summary(submission: Submission) -> SubmissionSummary:
    card = submission.card
    return SubmissionSummary(
        submission_code=submission.submission_code,
        status=submission.status,
        created_at=submission.created_at,
        card_name=card.card_name if card else None,
        game=card.game if card else None,
        mail_in=submission.mail_in,
        charged=submission.charged,
        scores={
            str(getattr(result.category, "value", result.category)): (
                float(result.raw_score) if result.raw_score is not None else None
            )
            for result in submission.analysis_results
            if result.side == AnalysisSide.combined
        },
    )


@router.get(
    "", response_model=list[SubmissionSummary], dependencies=[Depends(_submission_read_limit)]
)
def list_submissions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SubmissionSummary]:
    # selectinload: one query per relationship however many rows, rather
    # than one per row -- tests/test_submission_summary.py counts them.
    query = db.query(Submission).options(
        selectinload(Submission.card), selectinload(Submission.analysis_results)
    )
    if user.role != UserRole.operator:
        query = query.filter(Submission.user_id == user.id)
    return [_summary(s) for s in query.order_by(Submission.created_at.desc()).all()]


@router.get(
    "/{code}", response_model=SubmissionDetail, dependencies=[Depends(_submission_read_limit)]
)
def get_submission(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Submission:
    return _get_owned_submission(code, user, db)


@router.delete(
    "/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_submission_delete_limit)],
)
def delete_submission(
    code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    """Permanently delete a submission and everything belonging to it. The
    client owns their data, so this is allowed in any status -- the
    irreversibility is surfaced by a confirmation dialog in the UI."""
    submission = _get_owned_submission(code, user, db)
    submission_id = submission.id

    # Record that the deletion happened, but with no submission FK (the row
    # is about to vanish); the code lives in `detail` for the audit trail.
    db.add(
        AuditLog(
            submission_id=None,
            user_id=user.id,
            action="submission_deleted",
            detail={"deleted_code": code, "status": submission.status.value},
        )
    )
    # AuditLog.submission_id is a nullable FK with no ON DELETE cascade, so
    # any prior audit rows for this submission must be detached first or the
    # delete would violate the constraint. Nulling (not deleting) keeps the
    # history.
    db.query(AuditLog).filter(AuditLog.submission_id == submission_id).update(
        {AuditLog.submission_id: None}, synchronize_session=False
    )
    # The ORM cascade (cascade="all, delete-orphan") removes card, scans,
    # analysis results, comparisons, and reports; the on-disk folders are
    # not part of the DB and must be removed explicitly.
    db.delete(submission)
    db.commit()

    purge_submission_files(code)
    return None


@router.post(
    "/{code}/scans", response_model=SubmissionDetail, dependencies=[Depends(_scan_upload_limit)]
)
async def upload_scan(
    code: str,
    side: Literal["front", "back"] = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_verified_user),
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
    analysis runs.

    Those points are a region-of-interest hint, not the geometry: the card's
    edges are fitted from the image itself (see analysis/geometry.py), so the
    crop selects which card in the photo is meant and rejects the background,
    and no longer has to be placed accurately."""
    submission = _get_owned_submission(code, user, db)

    if submission.status not in _UPLOADABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Submission is '{submission.status.value}' -- scans can no longer be added",
        )
    if side in submission.scan_sides:
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {side} scan has already been uploaded")

    # Read one byte past the cap so the limit holds regardless of what
    # Content-Length claimed.
    content = await file.read(images.MAX_UPLOAD_BYTES + 1)
    try:
        suffix = images.validate_upload(content)
    except images.ImageTooLarge:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image is too large"
        ) from None
    except images.UnsupportedImage:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Unsupported image format -- use JPEG, PNG, or TIFF"
        ) from None
    # The watcher only picks up files it recognises, so refuse anything it
    # would silently ignore rather than writing an orphan into its folder.
    if suffix not in _IMAGE_SUFFIXES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Unsupported image format -- use JPEG, PNG, or TIFF"
        )

    folder = Path(config.scans_dir) / code
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / f"{side}{suffix}"
    # Re-encoded rather than written verbatim: a phone photo's EXIF can carry
    # the GPS coordinates of the customer's home, which this service has no
    # reason to hold. Pixels are preserved.
    file_path.write_bytes(images.strip_metadata(content, suffix))

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


@router.patch(
    "/{code}/card", response_model=SubmissionDetail, dependencies=[Depends(_card_update_limit)]
)
def update_card(
    code: str,
    payload: CardUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Name, set and number are labels -- nothing measured depends on them --
    so they edit in any status. Foil is part of the analysis
    (assessment.CARD_IS_FOIL), so it is locked once analysis has run: changing
    it afterwards would put a stale assessment beside a new declaration."""
    submission = _get_owned_submission(code, user, db)
    card = submission.card
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This submission has no card")

    fields = payload.model_fields_set
    if (
        "foil" in fields
        and payload.foil is not None
        and payload.foil != card.foil
        and submission.status not in PRE_ANALYSIS_STATUSES
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Foil can only be changed before the card is analysed -- it changes the result.",
        )

    for name in ("card_name", "set_name", "card_number"):
        if name in fields:
            value = getattr(payload, name)
            setattr(card, name, (value.strip() or None) if isinstance(value, str) else None)
    if "foil" in fields and payload.foil is not None:
        card.foil = payload.foil

    db.commit()
    db.refresh(submission)
    return submission


def _get_scan(submission: Submission, side: str) -> ScanImage:
    scan = next((s for s in submission.scan_images if s.side.value == side), None)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No {side} scan uploaded yet")
    return scan


@router.get("/{code}/scans/{side}/raw", dependencies=[Depends(_submission_image_limit)])
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


@router.get("/{code}/scans/{side}/suggest-crop", dependencies=[Depends(_crop_helper_limit)])
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
    has draggable handles to start from.

    Detects with the card's `expected_aspect`, computed exactly as `rectify`
    computes it -- `rectify` detects again inside the region of interest with
    that same aspect once this crop is submitted, and without it here the two
    calls can settle on different contours. Measured on two real photographs
    that cost: the untouched suggested crop disagreed with the fit by
    13-35mm and every boundary score was silently lost. See AGENTS.md's
    crop-guided-fit section.
    """
    submission = _get_owned_submission(code, user, db)
    scan = _get_scan(submission, side)
    width_mm, height_mm = scale.dimensions_for(
        db, submission.card.game if submission.card else None
    )
    expected_aspect = min(width_mm, height_mm) / max(width_mm, height_mm)
    try:
        image = preprocessing.load_image(scan.file_path)
        box, _info = preprocessing.detect_boundary(image, expected_aspect=expected_aspect)
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


@router.post("/{code}/scans/{side}/snap-crop", dependencies=[Depends(_crop_helper_limit)])
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
    user still confirms via confirm-crop.

    Passes the card's `expected_aspect` through to detection, for the same
    reason `suggest_crop` does -- see that endpoint's docstring."""
    submission = _get_owned_submission(code, user, db)
    scan = _get_scan(submission, side)
    _validate_points(payload, scan)
    width_mm, height_mm = scale.dimensions_for(
        db, submission.card.game if submission.card else None
    )
    expected_aspect = min(width_mm, height_mm) / max(width_mm, height_mm)
    image = preprocessing.load_image(scan.file_path)
    points = preprocessing.snap_points_to_boundary(
        image, [list(p) for p in payload.points], expected_aspect=expected_aspect
    )
    return {"points": points}


@router.post(
    "/{code}/scans/{side}/check-crop",
    response_model=CropCheckOut,
    dependencies=[Depends(_crop_helper_limit)],
)
def check_crop(
    code: str,
    side: Literal["front", "back"],
    payload: CropPointsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CropCheckOut:
    """Would this crop let the card's edges be fitted? Persists nothing.

    Exists because confirming a crop advances the state machine and spends the
    submission, so without this the first a customer hears about an unusable
    crop is a finished report with no scores in it. Measured across 30 real
    photographs: the fit falls back on 33% of uncropped images but only ~7%
    when the crop is traced around the card, and 8 of 10 failures are
    recovered by re-cropping alone. So the overwhelmingly common fix is one
    the customer can apply here, in seconds, before committing anything.

    Runs the pipeline's own `load_deskewed_card` rather than its own
    rectification. A check that disagreed with the thing it is checking --
    passing a crop analysis then declines, or refusing one it would have
    accepted -- would be worse than no check.
    """
    submission = _get_owned_submission(code, user, db)
    scan = _get_scan(submission, side)
    _validate_points(payload, scan)

    width_mm, height_mm = scale.dimensions_for(
        db, submission.card.game if submission.card else None
    )
    rectified = pipeline.load_deskewed_card(
        scan, width_mm, height_mm, crop_points=[list(point) for point in payload.points]
    )

    disqualifying = [
        code_
        for code_ in rectified.limitations
        if code_ in assessment.DISQUALIFYING_LIMITATIONS
    ]
    return CropCheckOut(
        boundary_found=not disqualifying,
        limitations=list(rectified.limitations),
        crop_disagreement_sides=list(rectified.geometry.get("crop_disagreement_sides", [])),
    )


@router.post(
    "/{code}/scans/{side}/confirm-crop",
    response_model=SubmissionDetail,
    dependencies=[Depends(_confirm_crop_limit)],
)
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

    # The slot is acquired before anything is saved, not after. A capacity
    # refusal (409/503) that landed after the crop was persisted would still
    # leave it stored -- saved crop points make the front "confirmed", and the
    # worker's poll analyses confirmed fronts without asking anyone, so a
    # refused request here would be followed by an unattended analysis and
    # charge with no quota check at all. Holding the slot first means a
    # refusal leaves nothing saved: the quota check, the crop save and the
    # analysis all happen inside it, or none of them do.
    with capacity.analysis_slot(user.id, code):
        # Before the crop is saved, not after: saved crop points make the front
        # "confirmed", and the worker's poll analyses confirmed fronts without
        # asking anyone -- so a refusal here that left them stored would be
        # followed by a charge past the limit anyway. A charged submission is
        # completing a check already paid for (typically adding its back).
        if submission.charged_at is None:
            quota = entitlements.get_quota(db, submission.user)
            if not quota.can_submit:
                db.commit()  # keep a rolled-forward window, as GET /quota does
                raise _quota_exhausted(quota)

        scan.crop_points = [list(point) for point in payload.points]
        db.commit()
        db.refresh(submission)

        confirmed = _confirmed_sides(submission)
        # The pipeline runs inside this call, so this is where request
        # concurrency becomes CPU concurrency -- see api/capacity.py for why a
        # 503 beats a hang here.
        submission = _advance_submission(db, submission, confirmed, {ScanSide(side)}, code)
    db.refresh(submission)
    return submission


@router.post(
    "/{code}/regions/toggle",
    response_model=SubmissionDetail,
    dependencies=[Depends(_submission_adjust_limit)],
)
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


@router.get("/{code}/scans/{side}/photo", dependencies=[Depends(_submission_image_limit)])
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
    # Resolved rather than named: derived images are JPEG now, and a submission
    # analysed before that change still has its PNG on disk.
    photo_path = artifacts.find(Path(config.reports_dir) / code, f"{side}_base")
    if photo_path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Photo not available yet")
    return FileResponse(photo_path, media_type=artifacts.media_type(photo_path))


@router.get(
    "/{code}/scans/{side}/regions/{category}/{region_id}/crop",
    dependencies=[Depends(_submission_image_limit)],
)
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
    crop_path = artifacts.find(
        Path(config.reports_dir) / code, f"{side}_{category}_{region_id}_crop"
    )
    if crop_path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Region crop not available")
    return FileResponse(crop_path, media_type=artifacts.media_type(crop_path))


@router.get("/{code}/report", dependencies=[Depends(_report_download_limit)])
def download_report(code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> FileResponse:
    submission = _get_owned_submission(code, user, db)
    reports = sorted(submission.reports, key=lambda r: r.version, reverse=True)
    if not reports:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No report generated yet")

    report = reports[0]
    if user.role != UserRole.operator and report.status != ReportStatus.published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not yet published")

    return FileResponse(report.pdf_path, media_type="application/pdf", filename=f"{code}.pdf")


@router.get(
    "/{code}/share", response_model=ShareStateOut, dependencies=[Depends(_share_manage_limit)]
)
def get_share(
    code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareStateOut:
    """Whether this submission is shared, and the link if it is.

    Its own endpoint rather than a field on SubmissionDetail, for two reasons.
    The model is returned straight from the ORM under `from_attributes`, so a
    derived field would need either a property on the model (which would import
    the sharing module, which imports the model) or a second copy of the URL
    building. And keeping the token off the detail payload means it is fetched
    only by the screen that shows it, rather than riding along on every read of
    every submission.
    """
    return sharing.share_state(_get_owned_submission(code, user, db))


@router.post(
    "/{code}/share", response_model=ShareStateOut, dependencies=[Depends(_share_manage_limit)]
)
def enable_share(
    code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareStateOut:
    """Turn on the public link for this submission.

    Idempotent: an already-shared submission gets its existing token back rather
    than a new one. Rotating is a separate, explicit call, because a customer
    pressing "share" twice must not silently kill the link they pasted somewhere
    a minute ago.

    Refused unless the latest report is published -- the same bar
    `download_report` sets for the customer's own download. A link handed to a
    stranger must not be able to show numbers that have not been reviewed, nor
    numbers that change under the same URL when they are.
    """
    submission = _get_owned_submission(code, user, db)
    if not sharing.is_publicly_visible(submission):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This report is not published yet, so it cannot be shared"
        )
    if submission.share_token is None:
        submission.share_token = sharing.new_token()
        submission.share_enabled_at = datetime.datetime.now(datetime.timezone.utc)
        db.add(
            AuditLog(
                submission_id=submission.id,
                user_id=user.id,
                # The token is deliberately absent from `detail`. The audit log
                # is readable in the admin panel, and a secret recorded there is
                # the same secret in a second place -- one that outlives the
                # rotation meant to kill it.
                action="share_enabled",
                detail={},
            )
        )
        db.commit()
        db.refresh(submission)
    return sharing.share_state(submission)


@router.post(
    "/{code}/share/rotate",
    response_model=ShareStateOut,
    dependencies=[Depends(_share_manage_limit)],
)
def rotate_share(
    code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ShareStateOut:
    """Issue a new token, killing every link already out there.

    This is the revoke-and-reshare path: a customer who posted a link somewhere
    they regret gets a working report back at a different address.
    """
    submission = _get_owned_submission(code, user, db)
    if submission.share_token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sharing is not enabled for this submission")
    submission.share_token = sharing.new_token()
    submission.share_enabled_at = datetime.datetime.now(datetime.timezone.utc)
    db.add(
        AuditLog(
            submission_id=submission.id,
            user_id=user.id,
            action="share_rotated",
            detail={},
        )
    )
    db.commit()
    db.refresh(submission)
    return sharing.share_state(submission)


@router.delete(
    "/{code}/share",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_share_manage_limit)],
)
def disable_share(
    code: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> None:
    """Stop sharing. Idempotent -- turning off something already off is a 204,
    not an error, so a client that lost track of the state can always get to
    "not shared" in one call."""
    submission = _get_owned_submission(code, user, db)
    if submission.share_token is not None:
        submission.share_token = None
        submission.share_enabled_at = None
        db.add(
            AuditLog(
                submission_id=submission.id,
                user_id=user.id,
                action="share_disabled",
                detail={},
            )
        )
        db.commit()


@router.post(
    "/{code}/approve",
    response_model=SubmissionDetail,
    dependencies=[Depends(_operator_publish_limit)],
)
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


@router.patch(
    "/{code}/auto-publish",
    response_model=SubmissionDetail,
    dependencies=[Depends(_operator_publish_limit)],
)
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


def _require_draft_under_review(submission: Submission) -> None:
    """Centering lines can only move while the draft is under review.

    The public share page renders from the database, not the PDF, so an
    adjustment after publication would change what a stranger sees with no
    operator review, and leave the published PDF disagreeing with the page.
    The same gate as toggle_region.
    """
    if submission.status != SubmissionStatus.draft_ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Submission is '{submission.status.value}' -- centering can only be adjusted while the draft is under review",
        )


def _centering_side_row(submission: Submission, side: str):
    return next(
        (
            r
            for r in submission.analysis_results
            if r.category == AnalysisCategory.centering and r.side.value == side
        ),
        None,
    )


@router.post(
    "/{code}/centering-adjust",
    response_model=SubmissionDetail,
    dependencies=[Depends(_submission_adjust_limit)],
)
def adjust_centering(
    code: str,
    payload: CenteringAdjustIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Move one side's centering border lines and rescore from where they now sit.

    The client sees where detection placed the four lines and can nudge each
    one. That is worth allowing because the border detector is the least
    reliable thing in the pipeline -- `border.TRANSITION_DELTA_E` fires on real
    print texture, and on a full-bleed back it has been seen reporting a
    9.6mm 'border' on one side and nothing on the other three.

    Movement is capped at the operator's `centering_adjust_limit_mm`, measured
    from where detection put each line, and the cap is enforced here rather
    than only in the UI: a limit that lives in the browser is a suggestion.
    Setting it to zero disables adjustment outright.

    Stored beside the measurement, never over it. The per-side row remains the
    record of what was actually measured; `recompute_submission` derives the
    combined score from measurement plus adjustment, so clearing the
    adjustment restores the detected figures exactly.

    On a side the pipeline declined for want of a printed frame, this places the
    lines instead (`centering.placement_eligible`): there is no detected line to
    bound against, so each line must sit within CENTERING_PLACEMENT_MAX_MM of the
    card's edge, and the result is scored and labelled as placed by hand.
    """
    submission = _get_owned_submission(code, user, db)
    _require_draft_under_review(submission)

    side_row = _centering_side_row(submission, payload.side)
    if side_row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"No centering analysis for the {payload.side}"
        )

    measured = side_row.measurements or {}
    scored = side_row.raw_score is not None
    placing = not scored and centering.placement_eligible(measured)
    # An unscored side that is not placeable -- above all one whose card edges
    # were never found -- has nothing trustworthy to put lines on. Accepting
    # would invent centering for a card the pipeline could not locate. Checked
    # ahead of the kill switch so "nothing to adjust" and "adjusting is off"
    # cannot be confused for each other.
    if not scored and not placing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Centering could not be measured on this side, so its lines cannot be adjusted.",
        )

    settings = get_or_create_settings(db)
    limit_mm = float(settings.centering_adjust_limit_mm or 0)
    if limit_mm <= 0:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Adjusting the centering lines is currently disabled."
        )

    proposed = {
        "left_px": payload.left_px,
        "right_px": payload.right_px,
        "top_px": payload.top_px,
        "bottom_px": payload.bottom_px,
    }
    rounded = {k: round(v, 1) for k, v in proposed.items()}

    mode, reason = recompute.check_centering_adjustment(measured, scored, rounded, limit_mm)
    if mode is None:
        code_, _, key = (reason or "").partition(":")
        if code_ == "no_scale":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This submission has no recorded scale to bound the move against.",
            )
        if code_ == "no_detected_width":
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"No detected {key} to adjust from on this side."
            )
        if code_ == "beyond_placement_bound":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"{key} is further than {scoring.CENTERING_PLACEMENT_MAX_MM:g}mm from the card's edge.",
            )
        if code_ == "no_axis":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Place at least one pair of opposite lines inside the card's edge.",
            )
        if code_ == "beyond_nudge_cap":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"{key} moved further than the {limit_mm:g}mm allowed."
            )
        # not_measurable is already handled above, before the kill switch; a
        # fresh instance here (or any other code) means the row changed under
        # us between the two checks, which the same message covers honestly.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Centering could not be measured on this side, so its lines cannot be adjusted.",
        )
    placing = mode == "place"

    if placing:
        detected_rounded = None
        cleared = False
    else:
        detected_rounded = {k: round(float(measured[k]), 1) for k in proposed}
        # Putting every line back where detection had it is not an adjustment,
        # so it clears rather than stores one -- see DELETE below for the
        # explicit form, which is the only one a placement has.
        cleared = rounded == detected_rounded

    adjustments = dict(submission.centering_adjustments or {})
    if cleared:
        adjustments.pop(payload.side, None)
    else:
        adjustments[payload.side] = rounded
    # NULL rather than {} when nothing is left, so `client_adjusted` (a plain
    # truthiness check) reads False again.
    submission.centering_adjustments = adjustments or None

    action = (
        "centering_placed"
        if placing
        else "centering_adjust_cleared" if cleared else "centering_adjusted"
    )
    db.add(
        AuditLog(
            submission_id=submission.id,
            user_id=user.id,
            action=action,
            detail={
                "side": payload.side,
                "detected": detected_rounded,
                "adjusted": None if cleared else rounded,
            },
        )
    )
    db.flush()

    recompute.recompute_submission(db, submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.delete(
    "/{code}/centering-adjust/{side}",
    response_model=SubmissionDetail,
    dependencies=[Depends(_submission_adjust_limit)],
)
def clear_centering_adjustment(
    code: str,
    side: Literal["front", "back"],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Submission:
    """Remove one side's centering adjustment or placement, and rescore.

    A placement has no detected lines to move back to, so "put every line where
    it was" cannot clear it the way it clears a nudge; this is the explicit way,
    and it works for both. Clearing a side with nothing stored changes nothing.

    Deliberately does not check the kill switch (`centering_adjust_limit_mm`):
    a customer can still withdraw a claim they made earlier even while
    adjusting is currently disabled, and refusing that would trap them with a
    number they no longer stand behind.
    """
    submission = _get_owned_submission(code, user, db)
    _require_draft_under_review(submission)

    adjustments = dict(submission.centering_adjustments or {})
    if side in adjustments:
        adjustments.pop(side)
        submission.centering_adjustments = adjustments or None
        side_row = _centering_side_row(submission, side)
        was_placement = side_row is not None and side_row.raw_score is None
        db.add(
            AuditLog(
                submission_id=submission.id,
                user_id=user.id,
                action="centering_placement_cleared" if was_placement else "centering_adjust_cleared",
                detail={"side": side},
            )
        )
        db.flush()
        recompute.recompute_submission(db, submission)

    db.commit()
    db.refresh(submission)
    return submission
