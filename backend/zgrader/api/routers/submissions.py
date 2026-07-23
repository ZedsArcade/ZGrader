import datetime
import io
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from zgrader.api.deps import get_current_user, require_operator
from zgrader.config import config
from zgrader.db import get_db
from zgrader.email.notifications import send_report_published, send_submission_received
from zgrader.models import (
    AuditLog,
    Card,
    ReportStatus,
    Settings,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)
from zgrader.reports import builder
from zgrader.schemas.admin import AutoPublishUpdate
from zgrader.schemas.submission import SubmissionCreate, SubmissionDetail, SubmissionSummary
from zgrader.worker.watcher import _IMAGE_SUFFIXES, process_submission_folder

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
    matches on, then runs the same processing function the watcher uses so
    the UI reflects the result immediately rather than waiting on a
    filesystem event or the poll safety net."""
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
    (folder / f"{side}{suffix}").write_bytes(content)

    process_submission_folder(db, code, folder)
    db.refresh(submission)
    return submission


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
