"""A check is charged when an analysis first scores the card, and only then.

It used to be charged at "Create submission", before any photo existed, so an
abandoned draft or a photo that never cropped still cost one. These pin the
rule from both directions: what charges, and everything that must not.
"""

import datetime
import shutil
from pathlib import Path

from zgrader import entitlements
from zgrader.analysis import pipeline
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models import (
    AnalysisCategory,
    AnalysisResult,
    AnalysisSide,
    AuditLog,
    Card,
    PlanEntitlement,
    Submission,
    SubmissionStatus,
    User,
)
from zgrader.models.subscription import Subscription, SubscriptionStatus
from zgrader.worker.watcher import process_submission_folder

from tests import checkflow_helpers as h


def test_creating_and_uploading_does_not_charge(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-none@example.com")
    code = h.create_code(token)
    assert h.upload(token, code, "front", sample_scan_paths["pokemon_front"]).status_code == 200

    assert h.quota(token)["remaining"] == 3
    assert h.quota(token)["resets_at"] is None
    assert h.detail(token, code)["charged"] is False


def test_a_scored_analysis_charges_once_and_opens_the_window(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-scored@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    resp = h.confirm(token, code, "front")

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "draft_ready"
    assert resp.json()["charged"] is True
    body = h.quota(token)
    assert body["used"] == 1
    assert body["resets_at"] is not None
    assert db_session.query(AuditLog).filter(AuditLog.action == "check_charged").count() == 1


def test_adding_the_back_does_not_charge_again(db_session, sample_scan_paths):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-back@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    h.confirm(token, code, "front")
    h.upload(token, code, "back", sample_scan_paths["pokemon_back"])

    assert h.confirm(token, code, "back").status_code == 200
    assert h.quota(token)["used"] == 1


def test_an_all_declined_result_is_free_and_a_later_scored_run_charges(
    db_session, sample_scan_paths, monkeypatch
):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-declined@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(None))
    front = h.confirm(token, code, "front")
    assert front.status_code == 200
    assert front.json()["charged"] is False
    assert h.quota(token)["remaining"] == 3

    h.upload(token, code, "back", sample_scan_paths["pokemon_back"])
    monkeypatch.setattr(pipeline, "run_analysis", h.fake_analysis(9.0))
    back = h.confirm(token, code, "back")
    assert back.json()["charged"] is True
    assert h.quota(token)["remaining"] == 2


def test_a_pipeline_error_is_free(db_session, sample_scan_paths, monkeypatch):
    h.set_free_limit(db_session, 3)
    token = h.login("charge-error@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    def boom(db, submission):
        raise pipeline.PipelineError("boom")

    monkeypatch.setattr(pipeline, "run_analysis", boom)
    resp = h.confirm(token, code, "front")

    assert resp.json()["status"] == "error"
    assert resp.json()["charged"] is False
    assert h.quota(token)["remaining"] == 3


def test_the_charge_is_claimed_once_even_when_asked_twice(db_session):
    """The API and the worker can both finish an analysis of one submission.
    The conditional UPDATE is what makes the second one a no-op."""
    user = User(email="charge-twice@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    db_session.add(user)
    db_session.flush()
    submission = Submission(submission_code="SUB-90901", user_id=user.id, status=SubmissionStatus.draft_ready)
    db_session.add(submission)
    db_session.flush()
    db_session.add(
        AnalysisResult(
            submission_id=submission.id,
            category=AnalysisCategory.corners,
            side=AnalysisSide.combined,
            raw_score=9.0,
            measurements={},
            flags={},
        )
    )
    db_session.flush()

    assert entitlements.charge_if_scored(db_session, submission) is True
    assert entitlements.charge_if_scored(db_session, submission) is False
    db_session.commit()
    db_session.refresh(user)
    assert user.quota_used == 1


def test_a_charge_on_an_unlimited_plan_spends_nothing(db_session, sample_scan_paths):
    """A subscription is a null submission_limit, not an exemption from being
    counted -- quota_used must stay 0 rather than track against nothing."""
    token = h.login("charge-unlimited@example.com")
    user = db_session.query(User).filter(User.email == "charge-unlimited@example.com").one()
    db_session.add(PlanEntitlement(plan="tier1", submission_limit=None, period_days=7))
    db_session.add(Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active))
    db_session.commit()

    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])

    resp = h.confirm(token, code, "front")

    assert resp.status_code == 200, resp.text
    assert resp.json()["charged"] is True
    db_session.refresh(user)
    assert user.quota_used == 0


def test_the_worker_charges_and_never_refuses(db_session, sample_scan_paths):
    """An operator drop has nowhere to send a 402, so it runs and charges even
    on an account that is already out of checks."""
    h.set_free_limit(db_session, 1)
    user = User(email="charge-worker@example.com", hashed_password=hash_password("hunter2pass"), is_verified=True)
    user.quota_used = 1
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.add(user)
    db_session.flush()
    submission = Submission(
        submission_code="SUB-90902", user_id=user.id, status=SubmissionStatus.created, mail_in=True
    )
    db_session.add(submission)
    db_session.flush()
    db_session.add(Card(submission_id=submission.id, game="Pokemon", card_name="Posted card"))
    db_session.commit()

    folder = Path(config.scans_dir) / "SUB-90902"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy(sample_scan_paths["pokemon_front"], folder / "front.png")
    process_submission_folder(db_session, "SUB-90902", folder)

    db_session.refresh(submission)
    db_session.refresh(user)
    assert submission.status == SubmissionStatus.draft_ready
    assert submission.charged_at is not None
    assert user.quota_used == 2
