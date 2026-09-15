"""Never-analysed photo drafts are deleted after a week untouched, photos and
all. Mail-in, charged, and already-analysed submissions are never touched."""

import datetime
from pathlib import Path

from sqlalchemy import update

from zgrader.config import config
from zgrader.models import ScanImage, Submission, SubmissionStatus
from zgrader.worker import main as worker_main

from tests import checkflow_helpers as h

OLD = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)


def _draft(db_session, token, sample_scan_paths, **fields) -> str:
    code = h.create_code(token, **fields)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    return code


def _age(db_session, code, *, submission=True, scans=True) -> None:
    row = db_session.query(Submission).filter(Submission.submission_code == code).one()
    if submission:
        db_session.execute(update(Submission).where(Submission.id == row.id).values(updated_at=OLD))
    if scans:
        db_session.execute(update(ScanImage).where(ScanImage.submission_id == row.id).values(updated_at=OLD))
    db_session.commit()


def _exists(db_session, code) -> bool:
    db_session.expire_all()
    return db_session.query(Submission).filter(Submission.submission_code == code).count() == 1


def test_a_stale_draft_and_its_photos_are_removed(db_session, sample_scan_paths):
    token = h.login("sweep-stale@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code)

    assert worker_main.purge_stale_drafts(db_session) == 1
    assert not _exists(db_session, code)
    assert not (Path(config.scans_dir) / code).exists()


def test_a_recent_photo_keeps_the_draft(db_session, sample_scan_paths):
    """Uploading writes a ScanImage, not the submission row -- keying on the
    submission alone would sweep a draft photographed yesterday."""
    token = h.login("sweep-recent-photo@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code, scans=False)

    assert worker_main.purge_stale_drafts(db_session) == 0
    assert _exists(db_session, code)


def test_mail_in_charged_and_analysed_rows_are_kept(db_session, sample_scan_paths):
    token = h.login("sweep-keep@example.com")
    mail_in = h.create_code(token, mail_in=True, card_name="Posted")
    charged = _draft(db_session, token, sample_scan_paths)
    analysed = _draft(db_session, token, sample_scan_paths)
    for code in (mail_in, charged, analysed):
        _age(db_session, code)
    db_session.execute(
        update(Submission)
        .where(Submission.submission_code == charged)
        .values(charged_at=OLD, updated_at=OLD)
    )
    db_session.execute(
        update(Submission)
        .where(Submission.submission_code == analysed)
        .values(status=SubmissionStatus.draft_ready, updated_at=OLD)
    )
    db_session.commit()

    assert worker_main.purge_stale_drafts(db_session) == 0
    for code in (mail_in, charged, analysed):
        assert _exists(db_session, code)


def test_a_failed_file_purge_keeps_the_row_for_the_next_pass(db_session, sample_scan_paths, monkeypatch):
    """The row names the directory. Delete it first and a failed purge leaves
    photos nothing can find."""
    token = h.login("sweep-purge-fails@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code)

    def refuse(code):
        raise PermissionError("read-only")

    monkeypatch.setattr(worker_main, "purge_submission_files", refuse)

    assert worker_main.purge_stale_drafts(db_session) == 0
    assert _exists(db_session, code)


def test_zero_disables_the_sweep(db_session, sample_scan_paths, monkeypatch):
    monkeypatch.setattr(config, "draft_retention_days", 0)
    token = h.login("sweep-disabled@example.com")
    code = _draft(db_session, token, sample_scan_paths)
    _age(db_session, code)

    assert worker_main.purge_stale_drafts(db_session) == 0
    assert _exists(db_session, code)


def test_a_database_error_on_one_draft_does_not_stop_the_sweep(db_session, sample_scan_paths, monkeypatch):
    """A transient DB error (OperationalError, IntegrityError) on one draft must
    not crash the sweep and stop photo analysis -- keep sweeping, skip that row,
    and retry it next pass."""
    import sqlalchemy.exc

    token = h.login("sweep-db-error@example.com")
    code1 = _draft(db_session, token, sample_scan_paths)
    code2 = _draft(db_session, token, sample_scan_paths)
    for code in (code1, code2):
        _age(db_session, code)

    # Make the first delete() call raise OperationalError, later calls work normally
    original_delete = db_session.delete
    call_count = [0]

    def delete_with_error(obj):
        call_count[0] += 1
        if call_count[0] == 1:
            raise sqlalchemy.exc.OperationalError("DELETE", {}, Exception("boom"))
        return original_delete(obj)

    monkeypatch.setattr(db_session, "delete", delete_with_error)

    # Should not raise; should sweep the second one successfully
    assert worker_main.purge_stale_drafts(db_session) == 1
    # Exactly one of the two should be gone
    assert _exists(db_session, code1) or _exists(db_session, code2)
    assert not (_exists(db_session, code1) and _exists(db_session, code2))
