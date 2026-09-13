"""A stand-in for zgrader.billing_stripe -- the only thing tests replace.

Everything above the adapter runs for real, including webhook signature
verification (construct_event is deliberately NOT faked; tests sign payloads
with the real scheme instead -- see sign()).
"""

import datetime
import hashlib
import hmac
import itertools
import time

from zgrader import billing_stripe
from zgrader.config import config

WEBHOOK_SECRET = "whsec_test_secret"
_counter = itertools.count(1)


def enable_billing(monkeypatch) -> None:
    monkeypatch.setattr(config, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(config, "stripe_webhook_secret", WEBHOOK_SECRET)


def _epoch(value: datetime.datetime) -> int:
    return int(value.timestamp())


def subscription_obj(
    *,
    user_id,
    sub_id: str = "sub_1",
    customer: str = "cus_1",
    plan: str = "monthly",
    status: str = "active",
    founder: bool = False,
    attempt_id=None,
    amount: int = 500,
    period_start: datetime.datetime | None = None,
    period_end: datetime.datetime | None = None,
    cancel_at: datetime.datetime | None = None,
    cancel_at_period_end: bool = False,
    created: int | None = None,
) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    start = period_start or now
    end = period_end or now + datetime.timedelta(days=30)
    metadata = {"user_id": str(user_id), "plan": plan, "founder": "true" if founder else "false"}
    if attempt_id is not None:
        metadata["checkout_attempt_id"] = str(attempt_id)
    return {
        "id": sub_id,
        "object": "subscription",
        "customer": customer,
        "status": status,
        "metadata": metadata,
        "created": created if created is not None else _epoch(now),
        "cancel_at": _epoch(cancel_at) if cancel_at else None,
        "cancel_at_period_end": cancel_at_period_end,
        "latest_invoice": "in_1",
        "items": {
            "data": [
                {
                    "price": {"unit_amount": amount},
                    "current_period_start": _epoch(start),
                    "current_period_end": _epoch(end),
                }
            ]
        },
    }


def sign(payload: bytes, secret: str = WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    """Stripe's real signature scheme: HMAC-SHA256 over "{t}.{body}"."""
    ts = timestamp or int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


class FakeStripe:
    def __init__(self) -> None:
        self.subscriptions: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []
        # Names of adapter functions that should raise on their next call.
        self.fail: set[str] = set()
        # Status expire_checkout_session should report for a given session id;
        # defaults to "expired", which is the ordinary supersede-and-retire case.
        self.session_status: dict[str, str] = {}

    def _record(self, call_name: str, **kw) -> None:
        # Positional, not `name=`: create_product's own `name` kwarg would
        # otherwise collide with this parameter (TypeError: multiple values
        # for argument 'name').
        self.calls.append((call_name, kw))
        if call_name in self.fail:
            raise RuntimeError(f"fake Stripe failure in {call_name}")

    def called(self, name: str) -> list[dict]:
        return [kw for n, kw in self.calls if n == name]

    def install(self, monkeypatch) -> "FakeStripe":
        for name in (
            "create_customer", "create_product", "create_checkout_session",
            "expire_checkout_session", "create_portal_session", "retrieve_subscription",
            "list_subscriptions", "delete_customer", "cancel_and_refund",
        ):
            monkeypatch.setattr(billing_stripe, name, getattr(self, name))
        return self

    def create_customer(self, *, user_id, email):
        self._record("create_customer", user_id=user_id, email=email)
        return {"id": f"cus_{user_id[:8]}"}

    def create_product(self, *, plan, name):
        self._record("create_product", plan=plan, name=name)
        return {"id": f"prod_{plan}"}

    def create_checkout_session(self, **params):
        self._record("create_checkout_session", **params)
        n = next(_counter)
        return {"id": f"cs_test_{n}", "url": f"https://checkout.stripe.test/c/{n}"}

    def expire_checkout_session(self, session_id):
        self._record("expire_checkout_session", session_id=session_id)
        return self.session_status.get(session_id, "expired")

    def create_portal_session(self, *, customer, return_url):
        self._record("create_portal_session", customer=customer, return_url=return_url)
        return {"url": f"https://billing.stripe.test/p/{customer}"}

    def retrieve_subscription(self, subscription_id):
        self._record("retrieve_subscription", subscription_id=subscription_id)
        return self.subscriptions.get(subscription_id)

    def list_subscriptions(self):
        self._record("list_subscriptions")
        return iter(list(self.subscriptions.values()))

    def delete_customer(self, customer_id):
        self._record("delete_customer", customer_id=customer_id)

    def cancel_and_refund(self, subscription_id):
        self._record("cancel_and_refund", subscription_id=subscription_id)
        sub = dict(self.subscriptions[subscription_id], status="canceled")
        self.subscriptions[subscription_id] = sub
        return sub, "pi_fake"
