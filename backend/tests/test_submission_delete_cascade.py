"""Deleting a submission must survive something else writing to it.

Production hit this as a 500:

    ForeignKeyViolation: update or delete on table "submissions" violates
    foreign key constraint "analysis_results_submission_id_fkey"

Every FK into `submissions` was ON DELETE NO ACTION, so the cascade lived in
the SQLAlchemy relationships: load the children, delete them, then delete the
parent. Anything inserting between those two statements strands a row and the
parent delete fails -- and this application has two writers that do exactly
that, the API's confirm-crop and the worker's watchdog and poll loop, with
nothing serialising them.

The tests below use a *second session* on purpose. A single-session test passes
against the old code and proves nothing, because the ORM cascade handles what
it can see; the bug only exists when someone else writes.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from zgrader.db import SessionLocal
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    AuditLog,
    Card,
    Submission,
    SubmissionStatus,
    User,
    UserRole,
)


def _submission_with_children(db_session, code: str) -> Submission:
    user = User(
        email=f"{code.lower()}@example.com", hashed_password="x", role=UserRole.client
    )
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code=code, user_id=user.id, status=SubmissionStatus.draft_ready
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Test"))
    db_session.add(
        AnalysisResult(
            submission_id=submission.id,
            side=AnalysisSide.front,
            category=AnalysisCategory.centering,
            raw_score=8.0,
            measurements={},
        )
    )
    db_session.add(
        AuditLog(submission_id=submission.id, user_id=user.id, action="created", detail={})
    )
    db_session.commit()
    return submission


def _insert_result_from_another_connection(submission_id: uuid.UUID) -> None:
    """What the worker does mid-delete: commit a new analysis row from a
    different session, in its own transaction."""
    other = SessionLocal()
    try:
        other.add(
            AnalysisResult(
                submission_id=submission_id,
                side=AnalysisSide.back,
                category=AnalysisCategory.corners,
                raw_score=7.0,
                measurements={},
            )
        )
        other.commit()
    finally:
        other.close()


def test_deleting_a_submission_removes_its_children(db_session):
    submission = _submission_with_children(db_session, "SUB-96001")
    submission_id = submission.id

    db_session.delete(submission)
    db_session.commit()

    assert db_session.get(Submission, submission_id) is None
    assert (
        db_session.query(AnalysisResult)
        .filter(AnalysisResult.submission_id == submission_id)
        .count()
        == 0
    )
    assert db_session.query(Card).filter(Card.submission_id == submission_id).count() == 0


def test_a_row_written_mid_delete_does_not_strand_the_submission(db_session):
    """The production failure, reproduced.

    The ORM reads the children, another connection commits a new one, and only
    then does the parent delete run. Under ON DELETE NO ACTION that raises
    ForeignKeyViolation; under CASCADE the database removes whatever is there
    at the moment the parent goes.
    """
    submission = _submission_with_children(db_session, "SUB-96002")
    submission_id = submission.id

    # Force the cascade to load the collection now, so the row below arrives
    # after the ORM has decided what to delete -- the interleaving that failed.
    assert len(submission.analysis_results) == 1
    db_session.delete(submission)
    _insert_result_from_another_connection(submission_id)

    db_session.commit()

    assert db_session.get(Submission, submission_id) is None
    assert (
        db_session.query(AnalysisResult)
        .filter(AnalysisResult.submission_id == submission_id)
        .count()
        == 0
    ), "a row written mid-delete outlived its submission"


def test_the_audit_trail_outlives_the_submission(db_session):
    """SET NULL rather than CASCADE: what happened to a submission is worth
    keeping once the submission is gone."""
    submission = _submission_with_children(db_session, "SUB-96003")
    submission_id = submission.id

    db_session.delete(submission)
    db_session.commit()

    rows = db_session.query(AuditLog).filter(AuditLog.action == "created").all()
    assert rows, "the audit row was deleted along with the submission"
    assert all(row.submission_id is None for row in rows)


def test_an_insert_after_the_delete_is_refused(db_session):
    """The other half of the guarantee. Once the submission is gone, a late
    write fails its own FK check instead of resurrecting an orphan."""
    submission = _submission_with_children(db_session, "SUB-96004")
    submission_id = submission.id
    db_session.delete(submission)
    db_session.commit()

    with pytest.raises(IntegrityError):
        _insert_result_from_another_connection(submission_id)
