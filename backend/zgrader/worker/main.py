"""Watcher worker entrypoint: a watchdog filesystem observer (debounced) plus
a periodic DB-poll safety net, per the plan's "no message broker" design --
watchdog catches new scans promptly, the poll loop catches anything a missed
filesystem event left behind (e.g. files dropped before this process started).
"""

import logging
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from zgrader.config import config
from zgrader.db import SessionLocal
from zgrader.models import Submission, SubmissionStatus
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


def run_forever() -> None:
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
    try:
        while True:
            for code in handler.pop_ready_codes():
                _process(code)

            now = time.monotonic()
            if now - last_poll >= config.worker_poll_interval_seconds:
                _poll_pending_submissions()
                last_poll = now

            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    run_forever()
