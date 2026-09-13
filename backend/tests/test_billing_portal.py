"""The Portal hand-off and the account page's view of a subscription."""

import datetime

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing
from tests.conftest import register_and_verify
from zgrader.api.main import app
from zgrader.models import Subscription, User

client = TestClient(app)
NOW = datetime.datetime.now(datetime.timezone.utc)


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _signed_in(db, email="portal@example.com", customer: str | None = None):
    headers = {"Authorization": f"Bearer {register_and_verify(client, email)}"}
    db.expire_all()
    user = db.query(User).filter_by(email=email).one()
    if customer:
        user.stripe_customer_id = customer
        db.commit()
    return headers, user


def test_every_billing_route_is_404_while_billing_is_off(db_session):
    headers, _ = _signed_in(db_session)
    assert client.post("/billing/portal", headers=headers).status_code == 404
    assert client.get("/billing/subscription", headers=headers).status_code == 404


def test_no_customer_means_nothing_to_manage(db_session, fake):
    headers, _ = _signed_in(db_session)
    assert client.post("/billing/portal", headers=headers).status_code == 409


def test_the_portal_returns_to_the_account_page(db_session, fake):
    headers, _ = _signed_in(db_session, customer="cus_9")
    resp = client.post("/billing/portal", headers=headers)
    assert resp.status_code == 200
    (call,) = fake.called("create_portal_session")
    assert call["customer"] == "cus_9" and call["return_url"].endswith("/account")


def test_no_subscription_reads_as_null(db_session, fake):
    headers, _ = _signed_in(db_session)
    resp = client.get("/billing/subscription", headers=headers)
    assert resp.status_code == 200 and resp.json() is None


def test_the_live_subscription_wins_over_a_newer_ended_one(db_session, fake):
    headers, user = _signed_in(db_session, customer="cus_9")
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_live", plan="monthly", status="past_due",
                                current_period_start=NOW - datetime.timedelta(days=30)))
    db_session.commit()
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_old", plan="annual", status="canceled"))
    db_session.commit()
    body = client.get("/billing/subscription", headers=headers).json()
    # Live but past its grace: shown, so the customer can fix the card, and
    # reported as not entitled, so the page can say so.
    assert (body["plan"], body["status"], body["entitled"]) == ("monthly", "past_due", False)
