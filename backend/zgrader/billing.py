"""Billing: what Stripe's state means for an account.

apply_subscription is the only code that writes `subscriptions`. The webhook,
the reconcile sweep and the admin reconcile button all end here, so there is
one set of rules and nowhere for a second, slightly different set to grow.

Nothing in this module trusts a figure from the browser or from an event
payload: amounts come from our own rows on the way out and from a fresh read
of Stripe on the way back.
"""

import datetime
import logging
import uuid

from sqlalchemy.orm import Session

from zgrader import billing_stripe
from zgrader.models import AuditLog, User
from zgrader.models.checkout_attempt import ATTEMPT_COMPLETED, ATTEMPT_OPEN, CheckoutAttempt
from zgrader.models.subscription import LIVE_STATUSES, Subscription

logger = logging.getLogger(__name__)


class BillingRefused(Exception):
    """A billing request the caller should be told no about, with the HTTP
    status that says why."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _ts(value: int | None) -> datetime.datetime | None:
    return datetime.datetime.fromtimestamp(value, tz=datetime.timezone.utc) if value else None


def _first_item(obj: dict) -> dict:
    items = (obj.get("items") or {}).get("data") or []
    return items[0] if items else {}


def _cancel_at(obj: dict) -> datetime.datetime | None:
    # Flexible billing mode sets cancel_at; classic sets cancel_at_period_end.
    if obj.get("cancel_at"):
        return _ts(obj["cancel_at"])
    if obj.get("cancel_at_period_end"):
        return _ts(_first_item(obj).get("current_period_end"))
    return None


def _audit(db: Session, user_id, action: str, detail: dict) -> None:
    # Never an email address in detail: delete_account scrubs addresses by key
    # name, so one under any new key would survive an erasure.
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))


def _owner(db: Session, obj: dict) -> User | None:
    metadata = obj.get("metadata") or {}
    try:
        user_id = uuid.UUID(str(metadata.get("user_id")))
    except ValueError:
        logger.info("subscription %s has no user in its metadata; not ours to mirror", obj.get("id"))
        return None
    user = db.get(User, user_id)
    if user is None:
        # An account deleted since -- its customer, and so this subscription,
        # were cancelled on the way out.
        logger.info("subscription %s names a user that no longer exists", obj.get("id"))
        return None
    if user.stripe_customer_id != obj.get("customer"):
        logger.warning(
            "subscription %s: metadata user %s does not own customer %s; ignoring",
            obj.get("id"), user.id, obj.get("customer"),
        )
        return None
    return user


def _other_live(db: Session, user_id, subscription_id: str) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status.in_(LIVE_STATUSES),
            Subscription.stripe_subscription_id != subscription_id,
        )
        .first()
    )


def _link_attempt(db: Session, row: Subscription, obj: dict, user: User) -> None:
    raw = (obj.get("metadata") or {}).get("checkout_attempt_id")
    if not raw or row.checkout_attempt_id is not None:
        return
    try:
        attempt = db.get(CheckoutAttempt, uuid.UUID(raw))
    except ValueError:
        return
    if attempt is None or attempt.user_id != user.id:
        return
    row.checkout_attempt_id = attempt.id
    row.terms_version = attempt.terms_version
    row.consented_at = attempt.consented_at
    if attempt.state == ATTEMPT_OPEN:
        attempt.state = ATTEMPT_COMPLETED


def apply_subscription(db: Session, obj: dict, *, source: str = "webhook") -> bool:
    """Mirror one subscription, as just read from Stripe. Returns whether
    anything changed. Flushes; never commits -- the caller owns the
    transaction, which is what lets the webhook record its event in the same
    one."""
    user = _owner(db, obj)
    if user is None:
        return False

    # Before any write: the partial unique index would otherwise reject the
    # upsert and the event would 500 on every retry for days.
    if obj["status"] in LIVE_STATUSES:
        other = _other_live(db, user.id, obj["id"])
        if other is not None:
            # Stripe doesn't guarantee event order, so the "other" row found
            # here might not actually be live any more -- re-read it rather
            # than trust what we last wrote.
            other_obj = billing_stripe.retrieve_subscription(other.stripe_subscription_id)
            if other_obj is None or other_obj["status"] not in LIVE_STATUSES:
                # The other row is stale, not a duplicate: end it in place,
                # no cancel and no refund.
                previous_status = other.status
                other.status = other_obj["status"] if other_obj is not None else "canceled"
                _audit(
                    db, user.id, "subscription_ended",
                    {
                        "stripe_subscription_id": other.stripe_subscription_id,
                        "plan": other.plan,
                        "founder": other.founder,
                        "status_before": previous_status,
                        "status_after": other.status,
                        "source": source,
                    },
                )
                db.flush()
            else:
                # Both are genuinely live: keep whichever is older by
                # Stripe's own created timestamp, not by arrival order. A
                # tie (should not happen; two subscriptions cannot share a
                # created second) resolves against the incoming one.
                if obj["created"] >= other_obj["created"]:
                    loser_id = obj["id"]
                else:
                    loser_id = other.stripe_subscription_id
                cancelled = billing_stripe.cancel_and_refund(loser_id)
                _audit(db, user.id, "subscription_duplicate_refunded", {"stripe_subscription_id": loser_id})
                if loser_id == obj["id"]:
                    obj = cancelled
                else:
                    # The loser is the row already in our database, not the
                    # one just read from Stripe -- mirror its new (cancelled)
                    # state now. Its status is no longer live, so this
                    # recursive call cannot re-enter this branch.
                    apply_subscription(db, cancelled, source=source)

    metadata = obj.get("metadata") or {}
    item = _first_item(obj)
    row = db.query(Subscription).filter(Subscription.stripe_subscription_id == obj["id"]).first()
    created = row is None
    if created:
        row = Subscription(user_id=user.id, stripe_subscription_id=obj["id"])
        db.add(row)
    before = None if created else (row.status, row.plan, row.founder, row.amount_pence, row.cancel_at,
                                   row.current_period_start, row.current_period_end)

    row.plan = metadata.get("plan") or row.plan or "unknown"
    row.founder = metadata.get("founder") == "true"
    row.status = obj["status"]
    row.amount_pence = (item.get("price") or {}).get("unit_amount")
    row.current_period_start = _ts(item.get("current_period_start"))
    row.current_period_end = _ts(item.get("current_period_end"))
    row.cancel_at = _cancel_at(obj)
    _link_attempt(db, row, obj, user)

    after = (row.status, row.plan, row.founder, row.amount_pence, row.cancel_at,
             row.current_period_start, row.current_period_end)
    changed = created or before != after
    if changed:
        detail = {
            "stripe_subscription_id": obj["id"],
            "plan": row.plan,
            "founder": row.founder,
            "status_before": None if before is None else before[0],
            "status_after": row.status,
            "source": source,
        }
        if created:
            action = "subscription_started"
        elif before[0] in LIVE_STATUSES and row.status not in LIVE_STATUSES:
            action = "subscription_ended"
        else:
            action = "subscription_changed"
        _audit(db, user.id, action, detail)
        if source == "reconcile":
            _audit(db, user.id, "billing_reconciled", detail)
            logger.warning("reconcile corrected subscription %s (%s)", obj["id"], action)
    db.flush()
    return changed
