"""What the shopfront and the operator's lookup learn about billing."""

from fastapi.testclient import TestClient

from tests.billing_fakes import enable_billing
from tests.conftest import register_and_verify
from zgrader.api.main import app
from zgrader.api.routers.auth import CURRENT_TERMS_VERSION
from zgrader.db import SessionLocal
from zgrader.models import Settings, Subscription, User, UserRole

client = TestClient(app)


def test_pricing_says_billing_is_off_by_default(db_session):
    body = client.get("/catalog/pricing").json()
    assert body["billing_enabled"] is False
    assert body["terms_version"] == CURRENT_TERMS_VERSION


def test_founder_seats_remaining_counts_founders(db_session, monkeypatch):
    enable_billing(monkeypatch)
    seats = db_session.query(Settings).one().founder_seats
    user = User(email="f@example.com", hashed_password="x", role=UserRole.client)
    db_session.add(user)
    db_session.flush()
    db_session.add(Subscription(user_id=user.id, stripe_subscription_id="sub_f", plan="annual", status="active", founder=True))
    db_session.commit()
    body = client.get("/catalog/pricing").json()
    assert body["billing_enabled"] is True
    assert body["founder_seats_remaining"] == seats - 1


def test_founder_seats_remaining_is_null_when_the_offer_is_off(db_session):
    db_session.query(Settings).one().founder_price_pence = None
    db_session.commit()
    assert client.get("/catalog/pricing").json()["founder_seats_remaining"] is None


def test_the_operator_lookup_shows_billing_state(db_session):
    headers = {"Authorization": f"Bearer {register_and_verify(client, 'op2@example.com')}"}
    with SessionLocal() as s:
        s.query(User).filter_by(email="op2@example.com").one().role = UserRole.operator
        customer = User(email="sub@example.com", hashed_password="x", role=UserRole.client)
        s.add(customer)
        s.flush()
        s.add(Subscription(user_id=customer.id, stripe_subscription_id="sub_s", plan="monthly", status="past_due", founder=False))
        s.commit()
    (row,) = client.get("/admin/users/quota?email=sub@", headers=headers).json()
    assert (row["subscription_status"], row["founder"], row["cancel_at"]) == ("past_due", False, None)
