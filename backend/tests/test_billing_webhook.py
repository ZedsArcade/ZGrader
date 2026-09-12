"""POST /billing/webhook: raw-body signatures, idempotency, order, failure."""

import json

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing, sign, subscription_obj
from zgrader.api.main import app
from zgrader.models import AuditLog, StripeEvent, Subscription, User, UserRole

client = TestClient(app)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


@pytest.fixture()
def customer(db_session):
    user = User(email="hook@example.com", hashed_password="x", role=UserRole.client, is_verified=True, stripe_customer_id="cus_1")
    db_session.add(user)
    db_session.commit()
    return user


def _event(obj: dict, *, event_id="evt_1", type_="customer.subscription.updated") -> dict:
    return {"id": event_id, "object": "event", "type": type_, "data": {"object": obj}}


def _post(event: dict | None = None, *, raw: bytes | None = None, sig: str | None = None, http=client):
    payload = raw if raw is not None else json.dumps(event).encode()
    return http.post(
        "/billing/webhook",
        content=payload,
        headers={"Stripe-Signature": sig if sig is not None else sign(payload), "Content-Type": "application/json"},
    )


def test_billing_off_is_404(db_session):
    assert _post(_event({"id": "sub_1"})).status_code == 404


def test_a_bad_signature_is_400_and_records_nothing(db_session, fake, customer):
    resp = _post(_event(subscription_obj(user_id=customer.id)), sig="t=1,v1=deadbeef")
    assert resp.status_code == 400
    assert db_session.query(StripeEvent).count() == 0
    assert fake.calls == []


def test_the_signature_covers_the_raw_bytes_not_the_parsed_json(db_session, fake, customer):
    """Signed as Stripe sent it, delivered after a parse and re-dump -- the
    same JSON, different bytes. Verifying anything but the raw body would
    accept this; the check must refuse it."""
    event = _event(subscription_obj(user_id=customer.id))
    signed = json.dumps(event, indent=2).encode()
    resp = _post(raw=json.dumps(event).encode(), sig=sign(signed))
    assert resp.status_code == 400


def test_a_valid_event_mirrors_what_stripe_says_now(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    assert _post(_event({"id": "sub_1"})).status_code == 200
    db_session.expire_all()
    assert db_session.query(Subscription).one().status == "active"
    assert db_session.query(StripeEvent).one().event_id == "evt_1"


def test_the_same_event_twice_changes_things_once(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    event = _event({"id": "sub_1"})
    assert _post(event).status_code == 200
    assert _post(event).status_code == 200
    assert len(fake.called("retrieve_subscription")) == 1
    db_session.expire_all()
    assert db_session.query(AuditLog).filter(AuditLog.action == "subscription_started").count() == 1


def test_events_out_of_order_end_in_stripes_current_state(db_session, fake, customer):
    # Stripe's truth: cancelled. The stale "created" arrives last and still
    # cannot resurrect it, because the handler re-reads rather than trusting
    # the payload.
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id, status="canceled")
    _post(_event({"id": "sub_1"}, event_id="evt_2"))
    stale = subscription_obj(user_id=customer.id, status="active")
    _post(_event(stale, event_id="evt_1", type_="customer.subscription.created"))
    db_session.expire_all()
    assert db_session.query(Subscription).one().status == "canceled"


def test_a_failure_rolls_back_the_event_so_the_retry_does_the_work(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    fake.fail.add("retrieve_subscription")
    lenient = TestClient(app, raise_server_exceptions=False)
    assert _post(_event({"id": "sub_1"}), http=lenient).status_code == 500
    db_session.expire_all()
    assert db_session.query(StripeEvent).count() == 0

    fake.fail.clear()
    assert _post(_event({"id": "sub_1"})).status_code == 200
    db_session.expire_all()
    assert db_session.query(Subscription).count() == 1


def test_an_expired_session_releases_its_attempt(db_session, fake, customer):
    import datetime

    from zgrader.models.checkout_attempt import ATTEMPT_EXPIRED, CheckoutAttempt

    now = datetime.datetime.now(datetime.timezone.utc)
    attempt = CheckoutAttempt(
        user_id=customer.id, plan="annual", amount_pence=3000, founder=True, terms_version="2026-09",
        consented_at=now, expires_at=now + datetime.timedelta(minutes=33), stripe_session_id="cs_9",
    )
    db_session.add(attempt)
    db_session.commit()
    session_obj = {"id": "cs_9", "object": "checkout.session", "metadata": {"checkout_attempt_id": str(attempt.id)}}
    assert _post(_event(session_obj, type_="checkout.session.expired")).status_code == 200
    db_session.expire_all()
    assert db_session.get(CheckoutAttempt, attempt.id).state == ATTEMPT_EXPIRED


def test_valid_deliveries_are_never_throttled_but_forgeries_are(db_session, fake, customer):
    fake.subscriptions["sub_1"] = subscription_obj(user_id=customer.id)
    for n in range(50):
        assert _post(_event({"id": "sub_1"}, event_id=f"evt_{n}")).status_code == 200
    statuses = [_post(_event({"id": "sub_1"}), sig="t=1,v1=bad").status_code for _ in range(25)]
    assert 429 in statuses
