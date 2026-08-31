"""Closing an account has to actually erase the person.

There was no test for `DELETE /auth/me` at all, which is a poor state for the
one endpoint the privacy policy points customers at. These cover the four
things that make it an erasure rather than a tidy-up:

  - the row, its submissions, and their files all go;
  - the audit trail survives with the identity taken out of it, *including*
    the two actions that record an address in `detail` rather than in the FK,
    which nulling user_id alone would leave behind;
  - a write arriving mid-delete does not strand the account, the same way
    test_submission_delete_cascade.py pins that property one level down;
  - an operator cannot delete themselves and leave the panel unreachable.
"""

import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import register_and_verify
from zgrader.api.main import app
from zgrader.config import config
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

client = TestClient(app)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _insert_submission_from_another_connection(user_id: uuid.UUID, code: str) -> None:
    """A row hanging off `users` committed from a different session, in its own
    transaction.

    It has to be a *Submission* to exercise `submissions.user_id`. Inserting an
    AnalysisResult instead proves nothing here: every FK into `submissions`
    already cascades (e2f7b1a94c56), so Postgres removes such a row when the
    submission goes no matter what the user-level FK says. The first version of
    this test made exactly that mistake and passed against the broken schema.
    """
    other = SessionLocal()
    try:
        other.add(
            Submission(
                submission_code=code, user_id=user_id, status=SubmissionStatus.created
            )
        )
        other.commit()
    finally:
        other.close()


def _insert_audit_row_from_another_connection(user_id: uuid.UUID) -> None:
    """An audit row naming the user, committed from a different session.

    The realistic writer for this one: `delete_account` nulls the person's
    audit rows and *then* deletes them, so anything writing a row with that
    user_id in the gap -- an operator adjusting quota, a login being recorded
    -- lands after the UPDATE has already passed over it.
    """
    other = SessionLocal()
    try:
        other.add(
            AuditLog(
                submission_id=None,
                user_id=user_id,
                action="written_mid_delete",
                detail={},
            )
        )
        other.commit()
    finally:
        other.close()


def _account_with_a_submission(db_session, email: str, code: str) -> tuple[User, Submission]:
    """A verified client account holding one submission with children and files
    on disk -- the shape a real closure has to cope with."""
    user = User(email=email, hashed_password="x", role=UserRole.client, is_verified=True)
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
    db_session.commit()

    for base in (config.scans_dir, config.reports_dir):
        folder = Path(base) / code
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "front.jpg").write_bytes(b"not really a jpeg")

    return user, submission


def _delete_via_api(db_session, user: User) -> None:
    """Drive the real endpoint for a user built directly in the fixture.

    Goes through the API rather than db_session.delete so the audit scrubbing
    in the router is exercised -- that logic is the point of these tests, and a
    bare ORM delete would skip it entirely.
    """
    from zgrader.auth.security import create_access_token

    token = create_access_token(str(user.id), user.token_version)
    db_session.commit()
    db_session.expunge_all()
    resp = client.delete("/auth/me", headers=_auth(token))
    assert resp.status_code == 204, resp.text


def test_deleting_an_account_removes_its_submissions_and_files(db_session):
    token = register_and_verify(client, "closer@example.com")

    resp = client.post(
        "/submissions",
        json={"game": "Pokemon", "card_name": "Pikachu"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["submission_code"]

    # Files the database knows nothing about. purge_submission_files is the
    # only thing that removes these, so an erasure that skipped it would leave
    # a customer's card photographs on disk with nothing pointing at them.
    for base in (config.scans_dir, config.reports_dir):
        folder = Path(base) / code
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "front.jpg").write_bytes(b"not really a jpeg")

    assert client.delete("/auth/me", headers=_auth(token)).status_code == 204

    with SessionLocal() as session:
        assert session.query(User).filter(User.email == "closer@example.com").one_or_none() is None
        assert (
            session.query(Submission).filter(Submission.submission_code == code).one_or_none()
            is None
        )

    assert not (Path(config.scans_dir) / code).exists()
    assert not (Path(config.reports_dir) / code).exists()


def test_the_audit_trail_survives_without_the_identity(db_session):
    user, submission = _account_with_a_submission(db_session, "audited@example.com", "SUB-97001")
    db_session.add(
        AuditLog(
            submission_id=submission.id,
            user_id=user.id,
            action="report_published",
            detail={"report_version": 1},
        )
    )
    db_session.commit()
    user_id = user.id

    _delete_via_api(db_session, user)

    with SessionLocal() as session:
        rows = session.query(AuditLog).filter(AuditLog.action == "report_published").all()
        assert rows, "the audit row was deleted along with the account"
        assert all(row.user_id is None for row in rows)
        assert all(row.submission_id is None for row in rows)

        closed = session.query(AuditLog).filter(AuditLog.action == "account_deleted").all()
        assert len(closed) == 1
        assert closed[0].user_id is None
        assert closed[0].detail == {"submissions_removed": 1}

        assert session.get(User, user_id) is None


def test_an_address_recorded_in_the_audit_body_is_scrubbed_too(db_session):
    """Nulling user_id is not enough on its own.

    `account_created_via_google` writes {"email": ...} and `user_quota_adjusted`
    writes {"target_email": ...}, so the address lives in the JSONB body rather
    than in the FK. Anonymising by nulling the FK alone leaves exactly the
    field an erasure request is about.
    """
    user, _ = _account_with_a_submission(db_session, "google-user@example.com", "SUB-97002")
    operator = User(
        email="op-scrub@example.com",
        hashed_password="x",
        role=UserRole.operator,
        is_verified=True,
    )
    db_session.add(operator)
    db_session.flush()

    db_session.add(
        AuditLog(
            submission_id=None,
            user_id=user.id,
            action="account_created_via_google",
            detail={"email": "google-user@example.com"},
        )
    )
    db_session.add(
        AuditLog(
            submission_id=None,
            user_id=operator.id,
            action="user_quota_adjusted",
            detail={
                "target_user_id": str(user.id),
                "target_email": "google-user@example.com",
                "plan": "free",
                "remaining_after": 3,
            },
        )
    )
    db_session.commit()

    _delete_via_api(db_session, user)

    with SessionLocal() as session:
        for row in session.query(AuditLog).all():
            assert "google-user@example.com" not in str(row.detail), (
                f"{row.action} still carries the deleted account's address: {row.detail}"
            )

        # The rest of the record is deliberately kept -- what happened still has
        # value, only who it happened to does not.
        quota = session.query(AuditLog).filter(AuditLog.action == "user_quota_adjusted").one()
        assert quota.detail["plan"] == "free"
        assert quota.detail["remaining_after"] == 3
        assert "target_email" not in quota.detail


def test_a_submission_written_mid_delete_does_not_strand_the_account(db_session):
    """The account-level twin of test_submission_delete_cascade.py.

    `submissions.user_id` was the one FK into `users` left without ON DELETE
    CASCADE, so closing an account was read-children-then-delete-parent -- the
    exact interleaving that failed in production one level down. A second
    session is required to see it: single-session, the ORM cascade covers what
    it can already see and the test passes against the broken schema.
    """
    user, submission = _account_with_a_submission(db_session, "raced@example.com", "SUB-97003")
    user_id = user.id
    submission_id = submission.id

    # Load the collection now, so the row below lands after the ORM has decided
    # what to remove.
    assert len(user.submissions) == 1
    db_session.delete(user)
    _insert_submission_from_another_connection(user_id, "SUB-97004")

    db_session.commit()

    with SessionLocal() as session:
        assert session.get(User, user_id) is None
        assert session.get(Submission, submission_id) is None
        assert (
            session.query(Submission).filter(Submission.user_id == user_id).count() == 0
        ), "a submission written mid-delete outlived the account it belonged to"
        assert (
            session.query(AnalysisResult)
            .filter(AnalysisResult.submission_id == submission_id)
            .count()
            == 0
        )


def test_an_audit_row_written_mid_delete_does_not_strand_the_account(db_session):
    """`audit_logs.user_id` had no ON DELETE behaviour either.

    `delete_account` nulls the person's audit rows and then deletes them, so a
    row written in the gap keeps a live FK to a user that is about to go. SET
    NULL makes the anonymisation structural rather than a matter of timing --
    and keeps the record, which is why it is not CASCADE.
    """
    user, _ = _account_with_a_submission(db_session, "audit-raced@example.com", "SUB-97005")
    user_id = user.id

    db_session.delete(user)
    _insert_audit_row_from_another_connection(user_id)

    db_session.commit()

    with SessionLocal() as session:
        assert session.get(User, user_id) is None
        row = session.query(AuditLog).filter(AuditLog.action == "written_mid_delete").one()
        assert row.user_id is None, "the late audit row still names a deleted account"


def test_an_operator_cannot_delete_themselves(db_session):
    """Losing the last operator leaves the admin panel unreachable, so this
    path refuses rather than letting someone lock the service open."""
    token = register_and_verify(client, "operator-self@example.com")
    with SessionLocal() as session:
        user = session.query(User).filter(User.email == "operator-self@example.com").one()
        user.role = UserRole.operator
        session.commit()

    resp = client.delete("/auth/me", headers=_auth(token))
    assert resp.status_code == 403

    with SessionLocal() as session:
        assert (
            session.query(User).filter(User.email == "operator-self@example.com").one_or_none()
            is not None
        )
