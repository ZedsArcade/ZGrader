"""Core, directly-testable folder-watching logic.

`process_submission_folder` is the unit both the real watchdog-based worker
(main.py) and tests call: given a submission code and its scan folder, it
registers any new front/back scan files -- auto-confirming their crop via
boundary detection, since operator flatbed drops are trusted input -- and
once a front scan is *confirmed*, runs the Phase 1 analysis pipeline and
applies the effective auto-publish setting (which requires both sides -- a
front-only "partial check" always lands in draft_ready, never auto-
published). The self-serve upload endpoint registers a scan (crop_points
NULL) without calling this function; analysis only starts once the user
confirms a crop via POST .../confirm-crop, which calls the shared
_advance_submission helper directly. It's idempotent and safe to call
repeatedly (e.g. once per watchdog event, or once per safety-net poll): it
no-ops once a submission reaches a terminal or in-flight state, and no-ops
on a draft_ready submission if nothing newly confirmed has arrived since the
draft was produced. A side newly confirmed after a draft already exists
(typically the back scan) clears that draft's stale results and reruns
analysis rather than duplicating rows.
"""

import datetime
import logging
import re
from pathlib import Path

from sqlalchemy.orm import Session

from zgrader.analysis import pipeline, preprocessing
from zgrader.email.notifications import send_report_published
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

# Terminal (published/error) or mid-processing -- process_submission_folder
# no-ops for these regardless of what's in the folder. Everything else
# (created/awaiting_scans/draft_ready) can still accept a newly-arrived
# scan side, since draft_ready may only reflect a front-only "partial
# check" with the back still to come.
_TERMINAL_OR_IN_FLIGHT_STATUSES = (
    SubmissionStatus.processing,
    SubmissionStatus.approved,
    SubmissionStatus.published,
    SubmissionStatus.error,
)


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
        # Operator flatbed-drop scans are trusted, controlled input (unlike
        # self-serve uploads, which start with crop_points=NULL and require
        # the manual crop-adjust UI) -- auto-confirming here keeps this
        # workflow exactly as zero-touch as before crop confirmation
        # existed: registered == confirmed == immediately analyzable. A
        # detection failure just leaves crop_points NULL, the same safe
        # degraded fallback the migration backfill uses.
        crop_points = None
        try:
            image = preprocessing.load_image(path)
            box, _info = preprocessing.detect_boundary(image)
            crop_points = box.tolist()
        except Exception:
            logger.warning("Boundary auto-detection failed for %s -- crop unconfirmed", path)

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
                crop_points=crop_points,
            )
        )
        existing_sides.add(side)
    db.flush()
    return warnings


def _confirmed_sides(submission: Submission) -> set[ScanSide]:
    """Sides with a confirmed crop (ScanImage.crop_points set) and
    therefore eligible for analysis -- see ScanImage.crop_points and
    Submission.confirmed_sides."""
    return {s.side for s in submission.scan_images if s.crop_points is not None}


def _effective_auto_publish(submission: Submission, settings: Settings | None) -> bool:
    if submission.auto_publish is not None:
        return submission.auto_publish
    return settings.auto_publish_default if settings else False


def _advance_submission(
    db: Session,
    submission: Submission,
    confirmed_sides: set[ScanSide],
    newly_confirmed: set[ScanSide],
    submission_code: str | None = None,
) -> Submission:
    """Run the has-front/draft_ready-rerun/analysis/auto-publish state
    machine given which sides are currently confirmed and which just
    became confirmed. Shared by process_submission_folder (operator
    flatbed-drop, where registration auto-confirms) and the self-serve
    confirm-crop endpoint (where a side becomes confirmed without any new
    file being registered)."""
    submission_code = submission_code or submission.submission_code
    has_front = ScanSide.front in confirmed_sides
    has_back = ScanSide.back in confirmed_sides

    if not has_front:
        if submission.status != SubmissionStatus.awaiting_scans:
            submission.status = SubmissionStatus.awaiting_scans
            db.commit()
        return submission

    if submission.status == SubmissionStatus.draft_ready:
        if not newly_confirmed:
            # Nothing changed since the analysis that already produced this
            # draft (e.g. a routine safety-net poll) -- stay idempotent.
            return submission
        # A side -- typically the back scan -- was confirmed after an earlier
        # front-only "partial check" already ran, so fall through and rerun.
        # Clearing the prior draft's rows used to happen here; run_analysis
        # now does it for every caller, which is what fixed the paths that
        # went through this module's guard and were never cleaned up.

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
    if has_back and _effective_auto_publish(submission, settings):
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
        send_report_published(submission.user, submission, settings)
        return submission

    db.commit()
    return submission


def process_submission_folder(db: Session, submission_code: str, folder: Path) -> Submission | None:
    submission = db.query(Submission).filter(Submission.submission_code == submission_code).first()
    if submission is None:
        logger.warning("No submission found for folder %s (code %s)", folder, submission_code)
        return None

    # Terminal or mid-processing -- idempotent no-op.
    if submission.status in _TERMINAL_OR_IN_FLIGHT_STATUSES:
        return submission

    if not folder.is_dir():
        return submission

    sides_before = _confirmed_sides(submission)
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

    sides_after = _confirmed_sides(submission)
    return _advance_submission(db, submission, sides_after, sides_after - sides_before, submission_code)
