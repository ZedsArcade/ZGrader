"""Closing an account must stop the billing before it removes the account.

Of the two orders that can fail halfway, only Stripe-first is safe: the other
leaves a card being charged with no account behind it and nobody to ask.
"""

import pytest
from fastapi.testclient import TestClient

from tests.billing_fakes import FakeStripe, enable_billing
from tests.conftest import register_and_verify
from zgrader import billing_stripe
from zgrader.api.main import app
from zgrader.db import SessionLocal
from zgrader.models import User

client = TestClient(app)
EMAIL = "leaving@example.com"


@pytest.fixture()
def fake(monkeypatch):
    enable_billing(monkeypatch)
    return FakeStripe().install(monkeypatch)


def _headers_with_customer(customer: str | None):
    headers = {"Authorization": f"Bearer {register_and_verify(client, EMAIL)}"}
    if customer:
        with SessionLocal() as s:
            s.query(User).filter_by(email=EMAIL).one().stripe_customer_id = customer
            s.commit()
    return headers


def _exists() -> bool:
    with SessionLocal() as s:
        return s.query(User).filter_by(email=EMAIL).count() == 1


def test_no_customer_deletes_without_calling_stripe(db_session, fake):
    headers = _headers_with_customer(None)
    assert client.delete("/auth/me", headers=headers).status_code == 204
    assert fake.called("delete_customer") == [] and not _exists()


def test_stripe_is_called_before_the_account_is_gone(db_session, fake, monkeypatch):
    headers = _headers_with_customer("cus_leaving")
    seen = []

    def delete_customer(customer_id):
        seen.append((customer_id, _exists()))

    monkeypatch.setattr(billing_stripe, "delete_customer", delete_customer)
    assert client.delete("/auth/me", headers=headers).status_code == 204
    assert seen == [("cus_leaving", True)]
    assert not _exists()


def test_a_stripe_failure_deletes_nothing(db_session, fake):
    headers = _headers_with_customer("cus_leaving")
    fake.fail.add("delete_customer")
    resp = client.delete("/auth/me", headers=headers)
    assert resp.status_code == 503
    assert "nothing has been deleted" in resp.json()["detail"]
    assert _exists()


def test_a_customer_with_billing_switched_off_is_refused(db_session):
    """Keys removed after someone subscribed: we cannot reach Stripe to stop
    the charges, so we must not remove the account that explains them."""
    headers = _headers_with_customer("cus_leaving")
    assert client.delete("/auth/me", headers=headers).status_code == 503
    assert _exists()
