"""Submission quotas, end to end.

tests/test_entitlements.py covers the rollover arithmetic in isolation. This
covers the parts that only exist once a database and a router are involved:
that the cap actually refuses, that refusing leaves nothing behind, and above
all that a spent credit stays spent.
"""

import datetime

from fastapi.testclient import TestClient

from zgrader.api.main import app
from zgrader.auth.security import hash_password
from zgrader.config import config
from zgrader.models import PlanEntitlement, Submission, User, UserRole
from zgrader.models.subscription import Subscription, SubscriptionStatus

from tests.conftest import register_and_verify

client = TestClient(app)


def _login(email: str) -> str:
    return register_and_verify(client, email)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create(token: str, name: str = "Pikachu"):
    return client.post(
        "/submissions", json={"game": "Pokemon", "card_name": name}, headers=_headers(token)
    )


def _set_free_limit(db_session, limit, period_days: int = 7) -> None:
    row = db_session.query(PlanEntitlement).filter(PlanEntitlement.plan == "free").one()
    row.submission_limit = limit
    row.period_days = period_days
    db_session.commit()


def _quota(token: str) -> dict:
    return client.get("/submissions/quota", headers=_headers(token)).json()


def test_quota_starts_full_with_no_countdown(db_session):
    """Before a first submission there is no open window, so nothing is
    counting down -- the whole allowance is simply available."""
    _set_free_limit(db_session, 3)
    token = _login("quota-fresh@example.com")

    body = _quota(token)
    assert body["plan"] == "free"
    assert body["unlimited"] is False
    assert body["limit"] == 3
    assert body["used"] == 0
    assert body["remaining"] == 3
    assert body["resets_at"] is None


def test_creating_a_submission_spends_one_credit_and_opens_the_window(db_session):
    _set_free_limit(db_session, 3)
    token = _login("quota-spend@example.com")

    assert _create(token).status_code == 201
    body = _quota(token)

    assert body["used"] == 1
    assert body["remaining"] == 2
    # The window opens on first use, so a reset time now exists.
    assert body["resets_at"] is not None


def test_exhausting_the_allowance_refuses_with_402(db_session):
    _set_free_limit(db_session, 2)
    token = _login("quota-exhaust@example.com")

    assert _create(token, "one").status_code == 201
    assert _create(token, "two").status_code == 201

    refused = _create(token, "three")
    assert refused.status_code == 402
    assert _quota(token)["remaining"] == 0


def test_a_refused_submission_leaves_nothing_behind(db_session):
    """The check runs before anything is created, so a refusal must not leave
    a half-made submission or an orphan scans folder on disk."""
    _set_free_limit(db_session, 1)
    token = _login("quota-nothing-behind@example.com")
    assert _create(token).status_code == 201

    before_rows = db_session.query(Submission).count()
    before_dirs = sorted(p.name for p in config.scans_dir.iterdir()) if config.scans_dir.exists() else []

    assert _create(token, "refused").status_code == 402

    db_session.expire_all()
    after_dirs = sorted(p.name for p in config.scans_dir.iterdir()) if config.scans_dir.exists() else []
    assert db_session.query(Submission).count() == before_rows
    assert after_dirs == before_dirs


def test_deleting_a_submission_does_not_refund_the_credit(db_session):
    """The reason usage is a counter rather than a COUNT(*) of live rows.

    Submissions can be deleted in any status, so deriving usage would hand the
    credit straight back -- and at zero remaining that is an unlimited-retry
    loop, available to anyone who noticed.
    """
    _set_free_limit(db_session, 1)
    token = _login("quota-no-refund@example.com")

    created = _create(token)
    assert created.status_code == 201
    code = created.json()["submission_code"]

    assert client.delete(f"/submissions/{code}", headers=_headers(token)).status_code == 204

    # The submission is gone...
    assert client.get(f"/submissions/{code}", headers=_headers(token)).status_code == 404
    # ...but the credit is not.
    assert _quota(token)["remaining"] == 0
    assert _create(token, "retry").status_code == 402


def test_an_unlimited_plan_is_never_refused(db_session):
    """How a subscription is expressed: a null limit on the plan."""
    token = _login("quota-unlimited@example.com")
    user = db_session.query(User).filter(User.email == "quota-unlimited@example.com").one()
    db_session.add(
        Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active)
    )
    db_session.commit()

    body = _quota(token)
    assert body["plan"] == "tier1"
    assert body["unlimited"] is True
    assert body["remaining"] is None
    assert body["resets_at"] is None

    # Comfortably past the free tier's cap.
    for i in range(5):
        assert _create(token, f"card {i}").status_code == 201
    assert _quota(token)["unlimited"] is True


def test_a_lapsed_subscription_falls_back_to_the_free_tier(db_session):
    _set_free_limit(db_session, 1)
    token = _login("quota-lapsed@example.com")
    user = db_session.query(User).filter(User.email == "quota-lapsed@example.com").one()
    subscription = Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active)
    db_session.add(subscription)
    db_session.commit()

    assert _quota(token)["unlimited"] is True

    subscription.status = SubscriptionStatus.canceled
    db_session.commit()

    body = _quota(token)
    assert body["plan"] == "free"
    assert body["unlimited"] is False
    # An unlimited plan never incremented the counter, so the free window
    # starts clean rather than already spent.
    assert body["remaining"] == 1


def test_the_window_rolls_forward_and_restores_the_allowance(db_session):
    _set_free_limit(db_session, 1, period_days=7)
    token = _login("quota-rollover@example.com")

    assert _create(token).status_code == 201
    assert _create(token, "refused").status_code == 402

    # Backdate the window past its end rather than waiting a week.
    user = db_session.query(User).filter(User.email == "quota-rollover@example.com").one()
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)
    db_session.commit()

    body = _quota(token)
    assert body["used"] == 0
    assert body["remaining"] == 1
    assert _create(token, "after reset").status_code == 201


def test_an_unknown_plan_falls_back_to_free_rather_than_unlimited(db_session):
    """A Stripe price nobody has configured here yet must not silently become
    an unlimited plan."""
    _set_free_limit(db_session, 1)
    token = _login("quota-unknown-plan@example.com")
    user = db_session.query(User).filter(User.email == "quota-unknown-plan@example.com").one()
    db_session.add(
        Subscription(user_id=user.id, plan="enterprise-2027", status=SubscriptionStatus.active)
    )
    db_session.commit()

    assert _quota(token)["unlimited"] is False
    assert _create(token).status_code == 201
    assert _create(token, "refused").status_code == 402


def test_quota_requires_authentication():
    assert client.get("/submissions/quota").status_code == 401
