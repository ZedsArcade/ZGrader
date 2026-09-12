"""POST /billing/checkout: refusals, amounts, founder seats, two tabs."""

import datetime
import threading

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing
from tests.conftest import register_and_verify
from zgrader import billing
from zgrader.api.main import app
from zgrader.api.routers.auth import CURRENT_TERMS_VERSION
from zgrader.db import SessionLocal
from zgrader.models import PlanEntitlement, Settings, Subscription, User
from zgrader.models.checkout_attempt import ATTEMPT_ABANDONED, CheckoutAttempt

client = TestClient(app)
NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _body(plan="monthly", **overrides):
    return {"plan": plan, "terms_version": CURRENT_TERMS_VERSION, "immediate_start_consent": True, **overrides}


def _auth(email="buyer@example.com"):
    return {"Authorization": f"Bearer {register_and_verify(client, email)}"}


def _user(db, email="buyer@example.com") -> User:
    db.expire_all()
    return db.query(User).filter(User.email == email).one()


def test_billing_off_is_404(db_session):
    assert client.post("/billing/checkout", json=_body(), headers=_auth()).status_code == 404


def test_an_amount_from_the_client_is_rejected(db_session, fake):
    resp = client.post("/billing/checkout", json=_body(amount_pence=1), headers=_auth())
    assert resp.status_code == 422
    assert fake.called("create_checkout_session") == []


@pytest.mark.parametrize(
    "overrides", [{"terms_version": "2000-01"}, {"immediate_start_consent": False}, {"plan": "pack"}, {"plan": "free"}, {"plan": "nope"}]
)
def test_refused_before_reaching_stripe(db_session, fake, overrides):
    resp = client.post("/billing/checkout", json=_body(**overrides), headers=_auth())
    assert resp.status_code == 422
    assert fake.calls == []


def test_an_unverified_account_is_refused(db_session, fake):
    """Same gate as submitting: an address nobody has confirmed does not get
    to start a payment in the account's name."""
    client.post("/auth/register", json={"email": "unv@example.com", "password": "hunter2pass", "accept_terms": True})
    token = client.post("/auth/login", data={"username": "unv@example.com", "password": "hunter2pass"}).json()["access_token"]
    resp = client.post("/billing/checkout", json=_body(), headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
    assert fake.calls == []


def test_a_live_subscription_is_409(db_session, fake):
    headers = _auth()
    user = _user(db_session)
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_x", plan="monthly", status="past_due"))
    db_session.commit()
    assert client.post("/billing/checkout", json=_body(), headers=headers).status_code == 409


def test_the_amount_is_the_plans_own_price(db_session, fake):
    resp = client.post("/billing/checkout", json=_body("monthly"), headers=_auth())
    assert resp.status_code == 200, resp.text
    assert resp.json()["url"].startswith("https://checkout.stripe.test/")

    (params,) = fake.called("create_checkout_session")
    price = db_session.query(PlanEntitlement).filter_by(plan="monthly").one().price_pence
    line = params["line_items"][0]["price_data"]
    assert (line["unit_amount"], line["currency"], line["recurring"]) == (price, "gbp", {"interval": "month"})
    meta = params["subscription_data"]["metadata"]
    user = _user(db_session)
    assert (meta["user_id"], meta["plan"], meta["founder"]) == (str(user.id), "monthly", "false")
    assert user.stripe_customer_id


def test_a_second_request_gets_the_same_session(db_session, fake):
    headers = _auth()
    first = client.post("/billing/checkout", json=_body(), headers=headers).json()["url"]
    second = client.post("/billing/checkout", json=_body(), headers=headers).json()["url"]
    assert first == second
    assert len(fake.called("create_checkout_session")) == 1
    assert len(fake.called("create_customer")) == 1


def test_annual_gets_the_founder_price_while_seats_remain(db_session, fake):
    client.post("/billing/checkout", json=_body("annual"), headers=_auth())
    (params,) = fake.called("create_checkout_session")
    settings = db_session.query(Settings).one()
    assert params["line_items"][0]["price_data"]["unit_amount"] == settings.founder_price_pence
    assert params["subscription_data"]["metadata"]["founder"] == "true"


def test_no_seats_left_means_full_price(db_session, fake):
    db_session.query(Settings).one().founder_seats = 0
    db_session.commit()
    client.post("/billing/checkout", json=_body("annual"), headers=_auth())
    (params,) = fake.called("create_checkout_session")
    annual = db_session.query(PlanEntitlement).filter_by(plan="annual").one()
    assert params["line_items"][0]["price_data"]["unit_amount"] == annual.price_pence


def test_monthly_is_never_founder_priced(db_session, fake):
    client.post("/billing/checkout", json=_body("monthly"), headers=_auth())
    (params,) = fake.called("create_checkout_session")
    assert params["subscription_data"]["metadata"]["founder"] == "false"


def test_a_stripe_failure_releases_the_seat(db_session, fake):
    fake.fail.add("create_checkout_session")
    settings = db_session.query(Settings).one()
    before = billing.founder_seats_remaining(db_session, settings)
    assert client.post("/billing/checkout", json=_body("annual"), headers=_auth()).status_code == 503
    db_session.expire_all()
    assert db_session.query(CheckoutAttempt).one().state == ATTEMPT_ABANDONED
    assert billing.founder_seats_remaining(db_session, db_session.query(Settings).one()) == before


def test_the_last_seat_cannot_be_taken_twice(db_session, fake):
    """Two sessions, as two concurrent requests would be. A decides under the
    Settings row lock and has not committed; B must wait for it, and then see
    the seat gone. Without FOR UPDATE, B does not block and both get it."""
    db_session.query(Settings).one().founder_seats = 1
    db_session.commit()
    register_and_verify(client, "a@example.com")
    register_and_verify(client, "b@example.com")

    a, b = SessionLocal(), SessionLocal()
    try:
        user_a = a.query(User).filter_by(email="a@example.com").one()
        user_b = b.query(User).filter_by(email="b@example.com").one()
        plan_a = a.query(PlanEntitlement).filter_by(plan="annual").one()
        plan_b = b.query(PlanEntitlement).filter_by(plan="annual").one()

        held = billing._decide_and_insert(a, user_a, plan_a, terms_version=CURRENT_TERMS_VERSION, now=NOW)
        result = {}
        worker = threading.Thread(
            target=lambda: result.update(
                b=billing.reserve_attempt(b, user_b, plan_b, terms_version=CURRENT_TERMS_VERSION, now=NOW)
            )
        )
        worker.start()
        worker.join(timeout=1.0)
        assert worker.is_alive(), "B did not wait for A's lock -- the seat count is racy"

        a.commit()
        worker.join(timeout=10.0)
        assert held.founder is True
        assert result["b"].founder is False
    finally:
        a.close()
        b.close()
