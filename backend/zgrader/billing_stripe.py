"""The only module that talks to Stripe.

Everything billing does to Stripe goes through a function here, for two
reasons. Tests replace these functions and nothing else, so no test needs the
network and no test mocks the SDK's internals. And the SDK's shape moves
between API versions -- recent ones moved the billing-period dates off the
subscription onto its items, and payments off the invoice -- so there is one
file to read when it moves again.

Every function returns plain dicts. How dict-like the SDK's StripeObject is
has changed across major versions; converting at the boundary means the rest
of the code indexes dicts and never has to care.
"""

import json
from collections.abc import Iterator

import stripe

from zgrader.config import config

#: The API version the SDK pins, recorded when this code was written against
#: it. The SDK sends its own pinned version with every request, so upgrading
#: the `stripe` package silently changes the shape of every object this file
#: returns. tests/test_billing_config.py fails when the two differ -- that is a
#: prompt to re-read this module against the new version, not to bump the
#: constant blindly.
STRIPE_API_VERSION = "2026-08-26.dahlia"

#: Seconds per Stripe request. The worker's reconcile shares a loop with scan
#: analysis, so a hung call must not stall it for the SDK's default 80s.
_TIMEOUT_SECONDS = 20

_configured = False


def _ready() -> None:
    global _configured
    if not config.billing_enabled:
        raise RuntimeError("Stripe is not configured on this deployment")
    if not _configured:
        stripe.api_key = config.stripe_secret_key
        stripe.max_network_retries = 2
        stripe.default_http_client = stripe.new_default_http_client(timeout=_TIMEOUT_SECONDS)
        _configured = True


def _plain(obj) -> dict:
    # StripeObject.__str__ is its JSON form in every SDK generation, which
    # makes this the one conversion that does not depend on the version.
    return json.loads(str(obj))


def _missing(exc: stripe.InvalidRequestError) -> bool:
    return getattr(exc, "code", None) == "resource_missing"


def create_customer(*, user_id: str, email: str) -> dict:
    _ready()
    # Idempotency key per user: a double-clicked Subscribe cannot create two
    # customers, because Stripe answers the second call with the first result.
    return _plain(
        stripe.Customer.create(
            email=email, metadata={"user_id": user_id}, idempotency_key=f"customer-{user_id}"
        )
    )


def create_product(*, plan: str, name: str) -> dict:
    _ready()
    return _plain(
        stripe.Product.create(
            name=name, metadata={"plan": plan}, idempotency_key=f"product-{plan}"
        )
    )


def create_checkout_session(**params) -> dict:
    _ready()
    return _plain(stripe.checkout.Session.create(**params))


def create_portal_session(*, customer: str, return_url: str) -> dict:
    _ready()
    return _plain(stripe.billing_portal.Session.create(customer=customer, return_url=return_url))


def retrieve_subscription(subscription_id: str) -> dict | None:
    _ready()
    try:
        return _plain(stripe.Subscription.retrieve(subscription_id))
    except stripe.InvalidRequestError as exc:
        if _missing(exc):
            return None
        raise


def list_subscriptions() -> Iterator[dict]:
    _ready()
    for sub in stripe.Subscription.list(status="all", limit=100).auto_paging_iter():
        yield _plain(sub)


def delete_customer(customer_id: str) -> None:
    """Deleting a customer cancels its subscriptions immediately. Already gone
    counts as done: the outcome the caller needs is 'nothing left to bill'."""
    _ready()
    try:
        stripe.Customer.delete(customer_id)
    except stripe.InvalidRequestError as exc:
        if not _missing(exc):
            raise


def cancel_and_refund(subscription_id: str) -> dict:
    """Cancel now and refund the first paid invoice payment in full.

    Only for the duplicate-subscription guard (spec §6.4). Invoices no longer
    carry their PaymentIntent directly; it is on the invoice's payments.
    """
    _ready()
    sub = stripe.Subscription.cancel(subscription_id)
    invoice_id = sub["latest_invoice"]
    if invoice_id:
        payments = stripe.InvoicePayment.list(invoice=invoice_id, status="paid", limit=10)
        for payment in payments.auto_paging_iter():
            intent = (payment["payment"] or {}).get("payment_intent")
            if intent:
                stripe.Refund.create(
                    payment_intent=intent, idempotency_key=f"duplicate-refund-{subscription_id}"
                )
                break
    return _plain(sub)


def construct_event(payload: bytes, sig_header: str) -> dict:
    """Verify a webhook against the raw body. Raises ValueError on anything
    that is not a correctly signed event, bad JSON included."""
    if not config.stripe_webhook_secret:
        raise ValueError("no webhook secret configured")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, config.stripe_webhook_secret)
    except stripe.SignatureVerificationError as exc:
        raise ValueError("signature verification failed") from exc
    return _plain(event)
