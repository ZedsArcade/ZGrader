"""The only module that talks to Stripe.

Everything billing does to Stripe goes through a function here, for two
reasons. Tests replace these functions and nothing else, so no test needs the
network and no test mocks the SDK's internals. And the SDK's shape moves
between API versions -- recent ones moved the billing-period dates off the
subscription onto its items, and payments off the invoice -- so there is one
file to read when it moves again.

Every function returns plain dicts. How dict-like the SDK's StripeObject is
has changed across major versions; converting at the boundary means the rest
of the code indexes dicts and never has to care. Never call a dict method
(`.get`, `.items`, ...) on a StripeObject itself -- convert with `_plain`
first. Stripe 15's objects are not dict subclasses, so `.get` raises
AttributeError; subscripting (`obj["x"]`) still works and is not a
substitute for the rest of dict's interface.
"""

import json
from collections.abc import Iterable, Iterator

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


def expire_checkout_session(session_id: str) -> str:
    """Retire a superseded checkout so a customer who changes plan never ends
    up with two payable sessions. Returns the session's resulting status
    ("expired" or "complete") rather than raising on an already-settled one --
    the caller decides what each status means."""
    _ready()
    session = _plain(stripe.checkout.Session.retrieve(session_id))
    if session["status"] == "open":
        session = _plain(stripe.checkout.Session.expire(session_id))
        return "expired"
    return session["status"]


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


def _paid_payment_intent(payments: Iterable[dict]) -> str | None:
    """The first payment_intent id among already-plain invoice-payment dicts,
    or None if none carries one (or the iterable is empty).

    Callers must convert every StripeObject with `_plain` before handing it
    here -- a raw StripeObject has no `.get`, which is exactly the bug this
    helper exists to make impossible to reintroduce."""
    for payment in payments:
        intent = (payment.get("payment") or {}).get("payment_intent")
        if intent:
            return intent
    return None


def cancel_and_refund(subscription_id: str) -> tuple[dict, str | None]:
    """Refund the latest invoice's paid payment in full, then cancel.

    Returns the cancelled subscription as a plain dict, and the refunded
    PaymentIntent id -- or None when nothing was refunded (no invoice, no
    paid payment on it, or a paid payment carrying no payment_intent).

    Only for the duplicate-subscription guard (spec §6.4) -- for a newly
    created duplicate, latest_invoice is its first (and only) invoice, so
    this refunds that one payment. Invoices no longer carry their
    PaymentIntent directly; it is on the invoice's payments.

    Refund runs *before* cancel, deliberately the reverse of the obvious
    order. The idempotency key makes a repeat refund safe, and the
    subscription stays live until cancel succeeds -- so if this raises
    between the two calls (a network error, say), the subscription is still
    live, the caller's transaction rolls back, and a retry re-reads it as
    live and re-enters the duplicate guard. Cancelling first would let a
    retry see the subscription already cancelled, skip the guard entirely,
    and leave the duplicate charge unrefunded forever.
    """
    _ready()
    sub = stripe.Subscription.retrieve(subscription_id)
    invoice_id = sub["latest_invoice"]
    refunded: str | None = None
    if invoice_id:
        payments = stripe.InvoicePayment.list(invoice=invoice_id, status="paid", limit=10)
        # Convert every listed payment before it ever meets a dict method --
        # see _paid_payment_intent and the module docstring.
        intent = _paid_payment_intent(_plain(payment) for payment in payments.auto_paging_iter())
        if intent:
            try:
                stripe.Refund.create(
                    payment_intent=intent, idempotency_key=f"duplicate-refund-{subscription_id}"
                )
            except stripe.InvalidRequestError as exc:
                # A retry outside the idempotency key's 24h window hits
                # an already-refunded charge; that is the outcome this
                # call wants, not a fresh failure. Either way the charge is
                # now refunded, so the caller may report it as such.
                if getattr(exc, "code", None) != "charge_already_refunded":
                    raise
            refunded = intent
    sub = stripe.Subscription.cancel(subscription_id)
    return _plain(sub), refunded


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
