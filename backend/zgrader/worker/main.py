"""Watcher worker entrypoint: a watchdog filesystem observer (debounced) plus
a periodic DB-poll safety net, per the plan's "no message broker" design --
watchdog catches new scans promptly, the poll loop catches anything a missed
filesystem event left behind (e.g. files dropped before this process started).
"""

import datetime
import logging
import time
from pathlib import Path

from sqlalchemy.orm import Session
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from zgrader.config import config
from zgrader.cpu import pin_analysis_threads
from zgrader.db import SessionLocal
from zgrader.models import ContactMessage, Submission, SubmissionStatus
from zgrader.seed import seed_all
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

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    run_forever()
