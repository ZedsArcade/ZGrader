"""Guards against calling a dict method on a StripeObject.

The reviewer's finding: `(payment["payment"] or {}).get("payment_intent")`
subscripts a StripeObject (which works) and then calls `.get` on the nested
StripeObject that comes back (which does not -- stripe 15.6.1's objects are
not dict subclasses). That crashed `cancel_and_refund` on every real call, so
the duplicate-subscription guard 500'd on every webhook retry.

These tests build real SDK objects with `stripe.InvoicePayment.construct_from`
rather than mocking anything, so they reproduce the actual AttributeError
rather than a stand-in for it. Only this file may import `stripe` outside of
`zgrader/billing_stripe.py` -- it needs the SDK to construct the objects it is
guarding against.
"""

import pytest
import stripe

from zgrader.billing_stripe import _paid_payment_intent

FAKE_KEY = "sk_test_x"


def test_first_paid_intent_among_plain_dicts():
    payments = [
        {"id": "ip_1", "payment": {"type": "charge", "payment_intent": "pi_1"}},
        {"id": "ip_2", "payment": {"type": "charge", "payment_intent": "pi_2"}},
    ]
    assert _paid_payment_intent(payments) == "pi_1"


def test_empty_iterable_has_no_intent():
    assert _paid_payment_intent([]) is None


def test_a_payment_without_an_intent_is_skipped():
    payments = [
        {"id": "ip_1", "payment": {"type": "charge"}},
        {"id": "ip_2", "payment": {"type": "charge", "payment_intent": "pi_2"}},
    ]
    assert _paid_payment_intent(payments) == "pi_2"


def test_a_payment_with_no_payment_field_at_all_is_skipped():
    payments = [{"id": "ip_1"}, {"id": "ip_2", "payment": {"payment_intent": "pi_2"}}]
    assert _paid_payment_intent(payments) == "pi_2"


def test_offline_reproduction_of_the_reviewers_finding():
    """This is the reviewer's own repro, turned into a permanent guard.

    Built with the real SDK's `construct_from` -- the object this produces is
    exactly what `stripe.InvoicePayment.list(...).auto_paging_iter()` yields
    in production. Feeding it to `_paid_payment_intent` WITHOUT converting it
    first must raise the SDK's own AttributeError, proving the helper's
    contract (plain dicts only) is not a formality: calling `.get` on the raw
    object is the exact crash `cancel_and_refund` used to hit on every call.
    """
    raw = stripe.InvoicePayment.construct_from(
        {"id": "ip_1", "payment": {"type": "charge", "payment_intent": "pi_construct"}},
        FAKE_KEY,
    )
    assert isinstance(raw, stripe.StripeObject)

    # The bug, reproduced: calling a dict method directly on the StripeObject
    # (or on the nested StripeObject its "payment" key holds) raises.
    with pytest.raises(AttributeError, match="dict method"):
        _paid_payment_intent([raw])  # type: ignore[list-item]

    # The fix: convert with _plain first (exactly what cancel_and_refund now
    # does before calling the helper), and it resolves cleanly.
    from zgrader.billing_stripe import _plain

    assert _paid_payment_intent([_plain(raw)]) == "pi_construct"


def test_a_payment_object_with_no_intent_constructed_via_the_sdk():
    raw = stripe.InvoicePayment.construct_from(
        {"id": "ip_1", "payment": {"type": "charge"}}, FAKE_KEY
    )
    from zgrader.billing_stripe import _plain

    assert _paid_payment_intent([_plain(raw)]) is None


def test_cancel_and_refund_survives_real_sdk_objects_end_to_end(monkeypatch):
    """Runs the actual `cancel_and_refund` -- not a stand-in for it -- against
    SDK-constructed objects standing in for what `stripe.Subscription.retrieve`,
    `stripe.InvoicePayment.list` and `stripe.Subscription.cancel` return in
    production.

    This is the test that a regression of the fix (feeding a raw StripeObject
    to `_paid_payment_intent` instead of a `_plain`-converted one) actually
    fails: the pure-dict tests above exercise the helper in isolation and
    would keep passing even if `cancel_and_refund` itself stopped converting.
    """
    from zgrader import billing_stripe
    from zgrader.config import config

    monkeypatch.setattr(config, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(config, "stripe_webhook_secret", "whsec_fake")
    monkeypatch.setattr(billing_stripe, "_configured", False)

    sub = stripe.Subscription.construct_from(
        {"id": "sub_1", "latest_invoice": "in_1", "status": "canceled"}, FAKE_KEY
    )
    payment = stripe.InvoicePayment.construct_from(
        {"id": "ip_1", "payment": {"type": "charge", "payment_intent": "pi_1"}}, FAKE_KEY
    )

    class FakeList:
        def auto_paging_iter(self):
            return iter([payment])

    monkeypatch.setattr(stripe.Subscription, "retrieve", staticmethod(lambda *a, **kw: sub))
    monkeypatch.setattr(stripe.Subscription, "cancel", staticmethod(lambda *a, **kw: sub))
    monkeypatch.setattr(stripe.InvoicePayment, "list", staticmethod(lambda *a, **kw: FakeList()))
    monkeypatch.setattr(stripe.Refund, "create", staticmethod(lambda *a, **kw: None))

    cancelled, refunded = billing_stripe.cancel_and_refund("sub_1")
    assert cancelled == {"id": "sub_1", "latest_invoice": "in_1", "status": "canceled"}
    assert refunded == "pi_1"
