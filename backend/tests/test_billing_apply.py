"""apply_subscription: the only code that writes billing state."""

import datetime

import pytest

from tests.billing_fakes import FakeStripe, enable_billing, subscription_obj
from zgrader import billing
from zgrader.models import AuditLog, Subscription, User, UserRole
from zgrader.models.checkout_attempt import ATTEMPT_COMPLETED, CheckoutAttempt

NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _customer(db, email="apply@example.com", cus="cus_1") -> User:
    user = User(email=email, hashed_password="x", role=UserRole.client, is_verified=True, stripe_customer_id=cus)
    db.add(user)
    db.flush()
    return user


def _audits(db, action):
    return db.query(AuditLog).filter(AuditLog.action == action).all()


def test_a_new_subscription_is_mirrored_and_audited(db_session, fake):
    user = _customer(db_session)
    start, end = NOW.replace(microsecond=0), (NOW + datetime.timedelta(days=365)).replace(microsecond=0)
    obj = subscription_obj(user_id=user.id, plan="annual", founder=True, amount=3000, period_start=start, period_end=end)

    assert billing.apply_subscription(db_session, obj) is True

    row = db_session.query(Subscription).one()
    assert (row.plan, row.status, row.founder, row.amount_pence) == ("annual", "active", True, 3000)
    assert (row.current_period_start, row.current_period_end) == (start, end)
    assert len(_audits(db_session, "subscription_started")) == 1


def test_reapplying_the_same_state_changes_nothing(db_session, fake):
    user = _customer(db_session)
    obj = subscription_obj(user_id=user.id)
    billing.apply_subscription(db_session, obj)
    assert billing.apply_subscription(db_session, obj) is False
    assert len(_audits(db_session, "subscription_changed")) == 0


def test_metadata_naming_someone_elses_customer_is_ignored(db_session, fake):
    user = _customer(db_session, cus="cus_mine")
    obj = subscription_obj(user_id=user.id, customer="cus_someone_else")
    assert billing.apply_subscription(db_session, obj) is False
    assert db_session.query(Subscription).count() == 0


def test_an_unknown_user_is_ignored(db_session, fake):
    import uuid

    assert billing.apply_subscription(db_session, subscription_obj(user_id=uuid.uuid4())) is False
    assert db_session.query(Subscription).count() == 0


def test_classic_cancel_at_period_end_becomes_a_cancel_date(db_session, fake):
    user = _customer(db_session)
    end = (NOW + datetime.timedelta(days=10)).replace(microsecond=0)
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, period_end=end, cancel_at_period_end=True))
    assert db_session.query(Subscription).one().cancel_at == end


def test_ending_is_audited_without_an_email_address(db_session, fake):
    user = _customer(db_session)
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id))
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, status="canceled"))
    ended = _audits(db_session, "subscription_ended")
    assert len(ended) == 1
    for row in db_session.query(AuditLog).filter(AuditLog.action.like("subscription_%")).all():
        assert "@" not in str(row.detail)


def test_a_second_live_subscription_is_cancelled_and_refunded(db_session, fake):
    user = _customer(db_session)
    old_created = int(NOW.timestamp()) - 100
    new_created = int(NOW.timestamp())
    fake.subscriptions["sub_old"] = subscription_obj(user_id=user.id, sub_id="sub_old", created=old_created)
    billing.apply_subscription(db_session, fake.subscriptions["sub_old"])
    fake.subscriptions["sub_new"] = subscription_obj(user_id=user.id, sub_id="sub_new", created=new_created)

    billing.apply_subscription(db_session, fake.subscriptions["sub_new"])
    db_session.flush()  # the partial unique index must not fire

    assert [c["subscription_id"] for c in fake.called("cancel_and_refund")] == ["sub_new"]
    statuses = {r.stripe_subscription_id: r.status for r in db_session.query(Subscription)}
    assert statuses == {"sub_old": "active", "sub_new": "canceled"}
    assert len(_audits(db_session, "subscription_duplicate_refunded")) == 1


def test_an_older_subscription_arriving_second_is_the_one_kept(db_session, fake):
    user = _customer(db_session)
    older_created = int(NOW.timestamp()) - 100
    newer_created = int(NOW.timestamp())
    fake.subscriptions["sub_newer"] = subscription_obj(user_id=user.id, sub_id="sub_newer", created=newer_created)
    fake.subscriptions["sub_older"] = subscription_obj(user_id=user.id, sub_id="sub_older", created=older_created)

    billing.apply_subscription(db_session, fake.subscriptions["sub_newer"])
    billing.apply_subscription(db_session, fake.subscriptions["sub_older"])
    db_session.flush()  # the partial unique index must not fire

    assert [c["subscription_id"] for c in fake.called("cancel_and_refund")] == ["sub_newer"]
    statuses = {r.stripe_subscription_id: r.status for r in db_session.query(Subscription)}
    assert statuses == {"sub_newer": "canceled", "sub_older": "active"}
    assert len(_audits(db_session, "subscription_duplicate_refunded")) == 1


def test_an_existing_row_stripe_no_longer_has_is_ended_not_refunded(db_session, fake):
    user = _customer(db_session)
    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, sub_id="sub_a"))
    # sub_a is deliberately left out of fake.subscriptions, so the guard's
    # re-read via retrieve_subscription returns None for it.

    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, sub_id="sub_b"))

    assert fake.called("cancel_and_refund") == []
    statuses = {r.stripe_subscription_id: r.status for r in db_session.query(Subscription)}
    assert statuses == {"sub_a": "canceled", "sub_b": "active"}
    assert len(_audits(db_session, "subscription_ended")) == 1


def test_the_checkout_attempt_carries_its_consent_onto_the_subscription(db_session, fake):
    user = _customer(db_session)
    attempt = CheckoutAttempt(
        user_id=user.id, plan="monthly", amount_pence=500, founder=False, terms_version="2026-09",
        consented_at=NOW, expires_at=NOW + datetime.timedelta(minutes=33), stripe_session_id="cs_1",
    )
    db_session.add(attempt)
    db_session.flush()

    billing.apply_subscription(db_session, subscription_obj(user_id=user.id, attempt_id=attempt.id))

    row = db_session.query(Subscription).one()
    assert (row.checkout_attempt_id, row.terms_version, row.consented_at) == (attempt.id, "2026-09", NOW)
    assert attempt.state == ATTEMPT_COMPLETED
