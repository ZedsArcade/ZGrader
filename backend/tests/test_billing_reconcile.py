"""Reconcile: the guarantee behind the webhook. When the stack is down,
Stripe retries for days and then stops; the bypass cannot help with that,
a sweep comparing us with Stripe can."""

import datetime

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing, subscription_obj
from tests.conftest import register_and_verify
from zgrader import billing, billing_stripe
from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import AuditLog, Subscription, User, UserRole
from zgrader.models.checkout_attempt import ATTEMPT_EXPIRED, CheckoutAttempt
from zgrader.worker import main as worker

client = TestClient(app)
NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


@pytest.fixture()
def customer(db_session):
    user = User(email="rec@example.com", hashed_password="x", role=UserRole.client, is_verified=True, stripe_customer_id="cus_1")
    db_session.add(user)
    db_session.commit()
    return user


def test_a_missed_cancellation_is_corrected_and_audited(db_session, fake, customer):
    billing.apply_subscription(db_session, subscription_obj(user_id=customer.id))
    db_session.commit()
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id, status="canceled")

    result = billing.reconcile(db_session)

    assert (result.checked, result.corrected) == (1, 1)
    assert db_session.query(Subscription).one().status == "canceled"
    assert db_session.query(AuditLog).filter(AuditLog.action == "billing_reconciled").count() == 1


def test_a_subscription_the_webhook_never_delivered_is_created(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    assert billing.reconcile(db_session).corrected == 1
    assert db_session.query(Subscription).one().status == "active"


def test_a_live_row_stripe_no_longer_has_is_ended(db_session, fake, customer):
    billing.apply_subscription(db_session, subscription_obj(user_id=customer.id, sub_id="sub_gone"))
    db_session.commit()
    # Not in fake.subscriptions: absent from the list, and retrieve says gone.
    billing.reconcile(db_session)
    row = db_session.query(Subscription).one()
    assert row.status == "canceled"
    assert row.amount_pence == 500, "ending a row must not erase what it recorded"


def test_nothing_to_fix_corrects_nothing(db_session, fake, customer):
    obj = subscription_obj(user_id=customer.id)
    billing.apply_subscription(db_session, obj)
    db_session.commit()
    fake.subscriptions["sub_1"] = obj
    assert billing.reconcile(db_session).corrected == 0


def test_expired_holds_are_closed(db_session, fake, customer):
    attempt = CheckoutAttempt(
        user_id=customer.id, plan="annual", amount_pence=3000, founder=True, terms_version="2026-09",
        consented_at=NOW - datetime.timedelta(hours=2), expires_at=NOW - datetime.timedelta(hours=1),
    )
    db_session.add(attempt)
    db_session.commit()
    billing.reconcile(db_session)
    db_session.refresh(attempt)
    assert attempt.state == ATTEMPT_EXPIRED


def test_reconcile_does_nothing_while_billing_is_off(db_session, monkeypatch):
    called = []
    monkeypatch.setattr(billing_stripe, "list_subscriptions", lambda: called.append(1) or iter(()))
    assert billing.reconcile(db_session) == billing.ReconcileResult()
    assert called == [], "reconcile reached for Stripe on a deployment with no keys"


def test_the_worker_survives_a_stripe_outage(db_session, fake, monkeypatch):
    def boom(db):
        raise RuntimeError("Stripe unreachable")

    monkeypatch.setattr(billing, "reconcile", boom)
    assert worker._reconcile_billing() is False  # logged, not raised


def test_the_admin_button_is_operator_only(db_session, fake):
    headers = {"Authorization": f"Bearer {register_and_verify(client, 'ops@example.com')}"}
    assert client.post("/admin/billing/reconcile", headers=headers).status_code == 403
    with SessionLocal() as s:
        s.query(User).filter_by(email="ops@example.com").one().role = UserRole.operator
        s.commit()
    resp = client.post("/admin/billing/reconcile", headers=headers)
    assert resp.status_code == 200 and resp.json() == {"checked": 0, "corrected": 0}
