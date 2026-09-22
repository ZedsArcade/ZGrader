"""Submission quotas, end to end.

tests/test_entitlements.py covers the rollover arithmetic in isolation. This
covers the parts that only exist once a database and a router are involved:
that the cap actually refuses, that refusing leaves nothing behind, and above
all that a spent credit stays spent.

A credit is spent when an analysis first scores a card, not at create --
tests/test_charge_on_score.py pins that rule. Here `h.spend` stands in for
checks already spent, so these tests stay about the cap itself.
"""

import datetime

from zgrader.config import config
from zgrader.models import PlanEntitlement, Submission, User
from zgrader.models.subscription import Subscription, SubscriptionStatus

from tests import checkflow_helpers as h


def test_quota_starts_full_with_no_countdown(db_session):
    """Before a first check there is no open window, so nothing is counting
    down -- the whole allowance is simply available."""
    h.set_free_limit(db_session, 3)
    token = h.login("quota-fresh@example.com")

    body = h.quota(token)
    assert body["plan"] == "free"
    assert body["unlimited"] is False
    assert body["limit"] == 3
    assert body["used"] == 0
    assert body["remaining"] == 3
    assert body["resets_at"] is None


def test_creating_a_submission_spends_nothing(db_session):
    h.set_free_limit(db_session, 3)
    token = h.login("quota-create@example.com")

    assert h.create(token).status_code == 201
    body = h.quota(token)
    assert body["used"] == 0
    assert body["resets_at"] is None


def test_an_exhausted_allowance_refuses_create_with_402(db_session):
    h.set_free_limit(db_session, 2)
    token = h.login("quota-exhaust@example.com")
    h.spend(db_session, "quota-exhaust@example.com", 2)

    refused = h.create(token)
    assert refused.status_code == 402
    assert refused.json()["detail"]["limit"] == 2
    assert h.quota(token)["remaining"] == 0


def test_a_refused_submission_leaves_nothing_behind(db_session):
    """The check runs before anything is created, so a refusal must not leave
    a half-made submission or an orphan scans folder on disk."""
    h.set_free_limit(db_session, 1)
    token = h.login("quota-nothing-behind@example.com")
    h.spend(db_session, "quota-nothing-behind@example.com", 1)

    before_rows = db_session.query(Submission).count()
    before_dirs = sorted(p.name for p in config.scans_dir.iterdir()) if config.scans_dir.exists() else []

    assert h.create(token).status_code == 402

    db_session.expire_all()
    after_dirs = sorted(p.name for p in config.scans_dir.iterdir()) if config.scans_dir.exists() else []
    assert db_session.query(Submission).count() == before_rows
    assert after_dirs == before_dirs


def test_deleting_a_submission_does_not_refund_the_credit(db_session, sample_scan_paths):
    """The reason usage is a counter rather than a COUNT(*) of live rows.

    Submissions can be deleted in any status, so deriving usage would hand the
    credit straight back -- and at zero remaining that is an unlimited-retry
    loop, available to anyone who noticed.
    """
    h.set_free_limit(db_session, 1)
    token = h.login("quota-no-refund@example.com")
    code = h.create_code(token)
    h.upload(token, code, "front", sample_scan_paths["pokemon_front"])
    assert h.confirm(token, code, "front").json()["charged"] is True

    assert h.client.delete(f"/submissions/{code}", headers=h.headers(token)).status_code == 204

    assert h.client.get(f"/submissions/{code}", headers=h.headers(token)).status_code == 404
    assert h.quota(token)["remaining"] == 0
    assert h.create(token).status_code == 402


def test_an_unlimited_plan_is_never_refused(db_session):
    """How a subscription is expressed: a null limit on the plan. Three
    creates, not more: the open-draft cap is a separate limit and applies to
    every plan."""
    token = h.login("quota-unlimited@example.com")
    user = db_session.query(User).filter(User.email == "quota-unlimited@example.com").one()
    db_session.add(PlanEntitlement(plan="tier1", submission_limit=None, period_days=7))
    db_session.add(Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active))
    db_session.commit()

    body = h.quota(token)
    assert body["plan"] == "tier1"
    assert body["unlimited"] is True
    assert body["remaining"] is None
    assert body["resets_at"] is None

    for i in range(3):
        assert h.create(token, card_name=f"card {i}").status_code == 201
    assert h.quota(token)["unlimited"] is True


def test_a_lapsed_subscription_falls_back_to_the_free_tier(db_session):
    h.set_free_limit(db_session, 1)
    token = h.login("quota-lapsed@example.com")
    user = db_session.query(User).filter(User.email == "quota-lapsed@example.com").one()
    db_session.add(PlanEntitlement(plan="tier1", submission_limit=None, period_days=7))
    subscription = Subscription(user_id=user.id, plan="tier1", status=SubscriptionStatus.active)
    db_session.add(subscription)
    db_session.commit()

    assert h.quota(token)["unlimited"] is True

    subscription.status = SubscriptionStatus.canceled
    db_session.commit()

    body = h.quota(token)
    assert body["plan"] == "free"
    assert body["unlimited"] is False
    assert body["remaining"] == 1


def test_the_window_rolls_forward_and_restores_the_allowance(db_session):
    h.set_free_limit(db_session, 1, period_days=7)
    token = h.login("quota-rollover@example.com")
    h.spend(db_session, "quota-rollover@example.com", 1)
    assert h.create(token).status_code == 402

    user = db_session.query(User).filter(User.email == "quota-rollover@example.com").one()
    user.quota_period_started_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=8)
    db_session.commit()

    body = h.quota(token)
    assert body["used"] == 0
    assert body["remaining"] == 1
    assert h.create(token).status_code == 201


def test_an_unknown_plan_falls_back_to_free_rather_than_unlimited(db_session):
    """A Stripe price nobody has configured here yet must not silently become
    an unlimited plan."""
    h.set_free_limit(db_session, 1)
    token = h.login("quota-unknown-plan@example.com")
    user = db_session.query(User).filter(User.email == "quota-unknown-plan@example.com").one()
    db_session.add(Subscription(user_id=user.id, plan="enterprise-2027", status=SubscriptionStatus.active))
    db_session.commit()

    assert h.quota(token)["unlimited"] is False
    h.spend(db_session, "quota-unknown-plan@example.com", 1)
    assert h.create(token).status_code == 402


def test_quota_requires_authentication():
    assert h.client.get("/submissions/quota").status_code == 401
