"""Watcher worker entrypoint: a watchdog filesystem observer (debounced) plus
a periodic DB-poll safety net, per the plan's "no message broker" design --
watchdog catches new scans promptly, the poll loop catches anything a missed
filesystem event left behind (e.g. files dropped before this process started).
"""

import datetime
import logging
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from zgrader import billing
from zgrader.config import config
from zgrader.cpu import pin_analysis_threads
from zgrader.db import SessionLocal
from zgrader.models import AuditLog, ContactMessage, ScanImage, Submission, SubmissionStatus
from zgrader.models.submission import PRE_ANALYSIS_STATUSES
from zgrader.seed import seed_all
from zgrader.storage import purge_submission_files
from zgrader.worker.watcher import SUBMISSION_CODE_RE, process_submission_folder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class _DebouncedHandler(FileSystemEventHandler):
    """Tracks the most recent filesystem event per submission folder and
    exposes codes that have been quiet for `debounce_seconds` -- avoids
    triggering analysis mid-write while the scanner is still saving front and
    back images into the same folder."""

    def __init__(self, debounce_seconds: float):
        self._debounce_seconds = debounce_seconds
        self._pending: dict[str, float] = {}

    def _touch(self, src_path: str) -> None:
        path = Path(src_path)
        candidate = path if path.is_dir() else path.parent
        if SUBMISSION_CODE_RE.match(candidate.name):
            self._pending[candidate.name] = time.monotonic()

    def on_created(self, event) -> None:
        self._touch(event.src_path)

    def on_modified(self, event) -> None:
        self._touch(event.src_path)

    def on_moved(self, event) -> None:
        self._touch(event.dest_path)

    def pop_ready_codes(self) -> list[str]:
        now = time.monotonic()
        ready = [code for code, ts in self._pending.items() if now - ts >= self._debounce_seconds]
        for code in ready:
            del self._pending[code]
        return ready


def _process(code: str) -> None:
    db = SessionLocal()
    try:
        process_submission_folder(db, code, Path(config.scans_dir) / code)
    finally:
        db.close()


def _poll_pending_submissions() -> None:
    db = SessionLocal()
    try:
        pending = (
            db.query(Submission)
            .filter(Submission.status.in_([SubmissionStatus.created, SubmissionStatus.awaiting_scans]))
            .all()
        )
        codes = [s.submission_code for s in pending]
    finally:
        db.close()

    for code in codes:
        _process(code)


#: How often the retention sweep runs. Deliberately unrelated to the
#: submission poll: this deletes at day granularity, so checking hourly is
#: already far finer than the promise it enforces, and running it every 30s
#: would be a pointless DELETE against a table nobody is writing to.
_RETENTION_SWEEP_INTERVAL_SECONDS = 3600.0

#: A full pass over Stripe once a day, plus one at every boot -- which means a
#: redeploy after an outage catches up on whatever Stripe stopped retrying.
_BILLING_RECONCILE_INTERVAL_SECONDS = 24 * 3600.0
#: After a failed pass (Stripe unreachable), try again sooner than a day.
_BILLING_RECONCILE_RETRY_SECONDS = 3600.0


def purge_expired_contact_messages(db: Session) -> int:
    """Delete contact enquiries past the configured retention window.

    Lives in the worker because it is the only process with a loop to hang it
    on -- the API is request-driven and would either never run it or run it on
    a stranger's request.

    `contact_messages` has no FK to `users` on purpose (the sender need not be
    logged in), which means account deletion cannot reach it. So this is the
    only thing that ever removes a name, an address, a message body and the IP
    stored beside them, and the privacy policy quotes its window.
    """
    days = config.contact_message_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    removed = (
        db.query(ContactMessage)
        .filter(ContactMessage.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return removed


def purge_stale_drafts(db: Session) -> int:
    """Delete photo drafts nobody has touched for `draft_retention_days`.

    A draft costs nothing until analysis scores it, so an abandoned one would
    otherwise keep a customer's photograph on this box forever for no reason.
    Mail-in submissions (the card is in the post), charged ones and anything
    already analysed are never touched.

    "Touched" is the later of the submission's and its newest photo's
    updated_at: an upload writes a ScanImage, not the submission row.

    Files go before the row, which names their directory -- a purge that
    fails after the row is gone leaves photos nothing can find. A failed
    purge keeps the row for the next pass.
    """
    days = config.draft_retention_days
    if days <= 0:
        return 0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    newest_photo = (
        select(func.max(ScanImage.updated_at))
        .where(ScanImage.submission_id == Submission.id)
        .scalar_subquery()
    )
    last_touched = func.greatest(Submission.updated_at, func.coalesce(newest_photo, Submission.updated_at))
    stale = (
        db.query(Submission)
        .filter(
            Submission.charged_at.is_(None),
            Submission.mail_in.is_(False),
            Submission.status.in_(PRE_ANALYSIS_STATUSES),
            last_touched < cutoff,
        )
        .all()
    )

    removed = 0
    for submission in stale:
        code = submission.submission_code
        try:
            purge_submission_files(code)
        except OSError:
            logger.warning("could not remove files for stale draft %s; kept for the next pass", code, exc_info=True)
            continue
        # A cleanup chore must not crash the process that analyses photos;
        # catch DB errors and keep sweeping, same rule as _reconcile_billing.
        try:
            db.query(AuditLog).filter(AuditLog.submission_id == submission.id).update(
                {AuditLog.submission_id: None}, synchronize_session=False
            )
            db.add(
                AuditLog(
                    submission_id=None,
                    user_id=submission.user_id,
                    action="draft_expired",
                    detail={"deleted_code": code},
                )
            )
            db.delete(submission)
            db.commit()
            removed += 1
        except SQLAlchemyError:
            db.rollback()
            logger.exception("could not delete stale draft %s; kept for the next pass", code)
            continue
    return removed


def _sweep_retention() -> None:
    db = SessionLocal()
    try:
        removed = purge_expired_contact_messages(db)
        if removed:
            logger.info(
                "purged %d contact message(s) older than %d days",
                removed,
                config.contact_message_retention_days,
            )
        drafts = purge_stale_drafts(db)
        if drafts:
            logger.info(
                "purged %d photo draft(s) untouched for %d days", drafts, config.draft_retention_days
            )
    finally:
        db.close()


def _reconcile_billing() -> bool:
    """Returns whether the pass completed. Never raises: this loop also runs
    scan analysis, and a Stripe outage must not stop or crash that."""
    if not config.billing_enabled:
        return True
    db = SessionLocal()
    try:
        result = billing.reconcile(db)
        log = logger.warning if result.corrected else logger.info
        log("billing reconcile: checked %d, corrected %d", result.checked, result.corrected)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("billing reconcile failed; retrying in an hour")
        return False
    finally:
        db.close()


def run_forever() -> None:
    # This process runs one analysis at a time, so it needs no semaphore -- but
    # it does need the same per-analysis thread limit as the API, or its single
    # analysis spreads across every core and the API's cap stops meaning
    # anything about the machine.
    pin_analysis_threads()

    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()

    scans_dir = Path(config.scans_dir)
    scans_dir.mkdir(parents=True, exist_ok=True)

    handler = _DebouncedHandler(config.watcher_debounce_seconds)
    observer = Observer()
    observer.schedule(handler, str(scans_dir), recursive=True)
    observer.start()
    logger.info("Watching %s for new scans", scans_dir)

    last_poll = 0.0
    # Starts at 0 so the first sweep happens at boot rather than an hour in --
    # a container that restarts more often than the interval would otherwise
    # never purge anything at all.
    last_sweep = 0.0
    # Starts at 0 for the same reason as last_sweep: the first pass at boot.
    last_reconcile = 0.0
    try:
        while True:
            for code in handler.pop_ready_codes():
                _process(code)

            now = time.monotonic()
            if now - last_poll >= config.worker_poll_interval_seconds:
                _poll_pending_submissions()
                last_poll = now

            if now - last_sweep >= _RETENTION_SWEEP_INTERVAL_SECONDS:
                _sweep_retention()
                last_sweep = now

            if now - last_reconcile >= _BILLING_RECONCILE_INTERVAL_SECONDS:
                ok = _reconcile_billing()
                last_reconcile = (
                    now if ok else now - _BILLING_RECONCILE_INTERVAL_SECONDS + _BILLING_RECONCILE_RETRY_SECONDS
                )

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    run_forever()
