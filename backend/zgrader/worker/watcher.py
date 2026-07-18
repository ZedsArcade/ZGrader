"""Core, directly-testable folder-watching logic.

`process_submission_folder` is the unit both the real watchdog-based worker
(main.py) and tests call: given a submission code and its scan folder, it
registers any new front/back scan files, and once a front scan is present,
runs the Phase 1 analysis pipeline and applies the effective auto-publish
setting. It's idempotent and safe to call repeatedly (e.g. once per watchdog
event, or once per safety-net poll) since it no-ops once a submission has
moved past the awaiting-scans stage.
"""

import datetime
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from zgrader.analysis import pipeline
from zgrader.models import (
    AuditLog,
    ReportStatus,
    ScanImage,
    ScanSide,
    Settings,
    Submission,
    SubmissionStatus,
)
from zgrader.reports import builder
from zgrader.scan_ingest import read_scan_metadata, sha256_file

logger = logging.getLogger(__name__)

SUBMISSION_CODE_RE = re.compile(r"^SUB-\d{5}$")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}


def _classify_side(filename: str) -> ScanSide | None:
    lower = filename.lower()
    if "front" in lower:
        return ScanSide.front
    if "back" in lower:
        return ScanSide.back
    return None


def _register_new_scans(db: Session, submission: Submission, folder: Path) -> list[str]:
    """Create ScanImage rows for new, classifiable image files in `folder`.
    Returns warning strings for files that couldn't be classified."""
    existing_paths = {s.file_path for s in submission.scan_images}
    existing_sides = {s.side for s in submission.scan_images}
    warnings: list[str] = []

    image_files = sorted(
        p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )
    for path in image_files:
        if str(path) in existing_paths:
            continue
        side = _classify_side(path.name)
        if side is None:
            warnings.append(
                f"Could not classify '{path.name}' as front/back scan "
                "(expected 'front' or 'back' in the filename) -- ignored."
            )
            continue
        if side in existing_sides:
            continue  # don't duplicate a side already registered

        width, height, dpi = read_scan_metadata(path)
        db.add(
            ScanImage(
                submission_id=submission.id,
                side=side,
                file_path=str(path),
                original_filename=path.name,
                dpi=dpi,
                width_px=width,
                height_px=height,
                checksum=sha256_file(path),
            )
        )
        existing_sides.add(side)
    db.flush()
    return warnings


def _effective_auto_publish(submission: Submission, settings: Settings | None) -> bool:
    if submission.auto_publish is not None:
        return submission.auto_publish
    return settings.auto_publish_default if settings else False


def process_submission_folder(db: Session, submission_code: str, folder: Path) -> Submission | None:
    submission = db.query(Submission).filter(Submission.submission_code == submission_code).first()
    if submission is None:
        logger.warning("No submission found for folder %s (code %s)", folder, submission_code)
        return None

    # Already processed (or mid-processing) -- idempotent no-op.
    if submission.status not in (SubmissionStatus.created, SubmissionStatus.awaiting_scans):
        return submission

    if not folder.is_dir():
        return submission

    warnings = _register_new_scans(db, submission, folder)
    # _register_new_scans reads submission.scan_images (to dedupe) before
    # adding new rows, which caches the pre-registration collection on the
    # instance -- new rows added via db.add() don't retroactively appear in
    # an already-loaded relationship, so it must be expired before the next
    # access re-queries it.
    db.expire(submission, ["scan_images"])
    if warnings:
        submission.notes = "\n".join(filter(None, [submission.notes, *warnings]))
        db.commit()

    has_front = any(s.side == ScanSide.front for s in submission.scan_images)
    if not has_front:
        if submission.status != SubmissionStatus.awaiting_scans:
            submission.status = SubmissionStatus.awaiting_scans
            db.commit()
        return submission

    try:
        pipeline.run_analysis(db, submission)
    except pipeline.PipelineError as exc:
        submission.status = SubmissionStatus.error
        submission.error_message = str(exc)
        db.add(AuditLog(submission_id=submission.id, user_id=None, action="pipeline_error", detail={"error": str(exc)}))
        db.commit()
        logger.exception("Pipeline failed for %s", submission_code)
        return submission

    settings = db.query(Settings).first()
    if _effective_auto_publish(submission, settings):
        report = builder.generate_report(db, submission)
        report.status = ReportStatus.published
        report.published_at = datetime.datetime.now(datetime.timezone.utc)
        submission.status = SubmissionStatus.published
        db.add(
            AuditLog(
                submission_id=submission.id,
                user_id=None,
                action="auto_published",
                detail={"report_version": report.version},
            )
        )

    db.commit()
    return submission
