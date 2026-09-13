"""Billing: what Stripe's state means for an account.

apply_subscription is the only code that writes `subscriptions`. The webhook,
the reconcile sweep and the admin reconcile button all end here, so there is
one set of rules and nowhere for a second, slightly different set to grow.

Nothing in this module trusts a figure from the browser or from an event
payload: amounts come from our own rows on the way out and from a fresh read
of Stripe on the way back.
"""

import dataclasses
import datetime
import logging
import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from zgrader import billing_stripe
from zgrader.config import config
from zgrader.models import AuditLog, PlanEntitlement, Settings, StripeEvent, User
from zgrader.models.checkout_attempt import (
    ATTEMPT_ABANDONED,
    ATTEMPT_COMPLETED,
    ATTEMPT_EXPIRED,
    ATTEMPT_OPEN,
    CheckoutAttempt,
)
from zgrader.models.subscription import LIVE_STATUSES, NEVER_PAID_STATUSES, Subscription

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


#: Stripe's Checkout session floor is 30 minutes; one more keeps clock skew
#: from turning a valid request into a rejected one.
SESSION_LIFETIME = datetime.timedelta(minutes=31)
#: A founder hold must outlive the session it holds a seat for.
HOLD_LIFETIME = datetime.timedelta(minutes=33)
_RECURRING = ("month", "year")


def founder_seats_taken(db: Session, now: datetime.datetime) -> int:
    """Founder subscriptions that ever paid, plus holds still open. A seat is
    never returned when a founder cancels: "the first N" means exactly that."""
    subscribed = (
        db.query(Subscription)
        .filter(Subscription.founder.is_(True), Subscription.status.notin_(NEVER_PAID_STATUSES))
        .count()
    )
    held = (
        db.query(CheckoutAttempt)
        .filter(
            CheckoutAttempt.founder.is_(True),
            CheckoutAttempt.state == ATTEMPT_OPEN,
            CheckoutAttempt.expires_at > now,
        )
        .count()
    )
    return subscribed + held


def founder_seats_remaining(db: Session, settings: Settings, now: datetime.datetime | None = None) -> int | None:
    """None when the offer is off, which is a different claim from zero."""
    if settings.founder_price_pence is None or settings.founder_seats is None:
        return None
    return max(0, settings.founder_seats - founder_seats_taken(db, now or _now()))


def _decide_and_insert(
    db: Session, user: User, plan: PlanEntitlement, *, terms_version: str, now: datetime.datetime
) -> CheckoutAttempt:
    """Decide founder-or-not and record the attempt, under the Settings row lock.

    Counting and inserting under one lock is what makes the last seat safe:
    a second checkout waits here until the first commits, then counts it.
    Does not commit -- reserve_attempt does, and the race test needs the gap.
    """
    settings = db.query(Settings).with_for_update().first()
    offer = (
        plan.billing_period == "year"
        and settings is not None
        and settings.founder_price_pence is not None
        and settings.founder_seats is not None
    )
    founder = bool(offer and founder_seats_taken(db, now) < settings.founder_seats)
    attempt = CheckoutAttempt(
        user_id=user.id,
        plan=plan.plan,
        amount_pence=settings.founder_price_pence if founder else plan.price_pence,
        founder=founder,
        terms_version=terms_version,
        consented_at=now,
        expires_at=now + HOLD_LIFETIME,
        state=ATTEMPT_OPEN,
    )
    db.add(attempt)
    db.flush()
    return attempt


def reserve_attempt(
    db: Session, user: User, plan: PlanEntitlement, *, terms_version: str, now: datetime.datetime
) -> CheckoutAttempt:
    attempt = _decide_and_insert(db, user, plan, terms_version=terms_version, now=now)
    db.commit()
    return attempt


def _ensure_customer(db: Session, user: User) -> str:
    if not user.stripe_customer_id:
        user.stripe_customer_id = billing_stripe.create_customer(user_id=str(user.id), email=user.email)["id"]
        db.commit()
    return user.stripe_customer_id


def _ensure_product(db: Session, plan: PlanEntitlement, business_name: str) -> str:
    if not plan.stripe_product_id:
        name = f"{business_name} — {plan.plan.capitalize()}"
        plan.stripe_product_id = billing_stripe.create_product(plan=plan.plan, name=name)["id"]
        db.commit()
    return plan.stripe_product_id


def _has_live(db: Session, user: User) -> bool:
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status.in_(LIVE_STATUSES))
        .first()
        is not None
    )


def create_checkout(db: Session, user: User, *, plan_name: str, terms_version: str) -> str:
    """A Checkout session URL for this user and plan. The caller has already
    checked billing is on and that the Terms version and consent are current."""
    plan = db.query(PlanEntitlement).filter(PlanEntitlement.plan == plan_name).first()
    if plan is None or plan.price_pence is None or plan.billing_period not in _RECURRING:
        raise BillingRefused(422, "That plan can't be bought here.")
    if _has_live(db, user):
        raise BillingRefused(409, "You already have a subscription — manage it from your account page.")

    now = _now()
    # Alive means the *Stripe session* has not expired, not just the hold:
    # the hold outlives the session by (HOLD_LIFETIME - SESSION_LIFETIME) so a
    # founder seat is never released early, but that gap is exactly the
    # window in which reusing the row would hand back an already-dead URL.
    open_attempt = (
        db.query(CheckoutAttempt)
        .filter(
            CheckoutAttempt.user_id == user.id,
            CheckoutAttempt.state == ATTEMPT_OPEN,
            CheckoutAttempt.expires_at > now + (HOLD_LIFETIME - SESSION_LIFETIME),
            CheckoutAttempt.stripe_session_url.isnot(None),
        )
        .order_by(CheckoutAttempt.created_at.desc())
        .first()
    )
    if open_attempt is not None:
        if open_attempt.plan == plan.plan:
            # Two tabs on the same plan must be one checkout, not two.
            return open_attempt.stripe_session_url
        # Changed their mind about the plan: the old session must never stay
        # payable alongside the new one, or the customer could complete both.
        try:
            outcome = billing_stripe.expire_checkout_session(open_attempt.stripe_session_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("could not retire the superseded checkout session")
            raise BillingRefused(503, "Payments are unavailable right now. Please try again shortly.") from exc
        if outcome == "complete":
            raise BillingRefused(409, "A checkout you started has just completed — see your account page.")
        open_attempt.state = ATTEMPT_EXPIRED
        db.commit()

    try:
        customer = _ensure_customer(db, user)
        product = _ensure_product(db, plan, db.query(Settings).one().business_name)
    except Exception as exc:  # noqa: BLE001 -- any Stripe failure is a 503 to the customer
        logger.exception("could not prepare Stripe customer/product for checkout")
        raise BillingRefused(503, "Payments are unavailable right now. Please try again shortly.") from exc

    attempt = reserve_attempt(db, user, plan, terms_version=terms_version, now=now)
    try:
        session = billing_stripe.create_checkout_session(
            mode="subscription",
            customer=customer,
            client_reference_id=str(user.id),
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "gbp",
                        "product": product,
                        "unit_amount": attempt.amount_pence,
                        "recurring": {"interval": plan.billing_period},
                    },
                }
            ],
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                    "plan": plan.plan,
                    "founder": "true" if attempt.founder else "false",
                    "checkout_attempt_id": str(attempt.id),
                }
            },
            metadata={"checkout_attempt_id": str(attempt.id)},
            expires_at=int((now + SESSION_LIFETIME).timestamp()),
            success_url=f"{config.site_url}/account?billing=success",
            cancel_url=f"{config.site_url}/pricing",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stripe refused to create a checkout session")
        attempt.state = ATTEMPT_ABANDONED
        db.commit()
        raise BillingRefused(503, "Payments are unavailable right now. Please try again shortly.") from exc

    attempt.stripe_session_id = session["id"]
    attempt.stripe_session_url = session["url"]
    db.commit()
    return session["url"]


HANDLED_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "checkout.session.expired",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


def _close_attempt(db: Session, session_obj: dict, state: str) -> None:
    attempt = None
    raw = (session_obj.get("metadata") or {}).get("checkout_attempt_id")
    if raw:
        try:
            attempt = db.get(CheckoutAttempt, uuid.UUID(raw))
        except ValueError:
            attempt = None
    if attempt is None and session_obj.get("id"):
        attempt = db.query(CheckoutAttempt).filter(CheckoutAttempt.stripe_session_id == session_obj["id"]).first()
    if attempt is not None and attempt.state == ATTEMPT_OPEN:
        attempt.state = state


def _apply_current(db: Session, subscription_id: str, fallback: dict) -> None:
    """Re-read the subscription rather than trusting the event: deliveries
    arrive out of order, and the newest truth is Stripe's, not the payload's.
    Only a subscription Stripe no longer has falls back to the payload -- and
    then only to record that it ended."""
    current = billing_stripe.retrieve_subscription(subscription_id)
    apply_subscription(db, current if current is not None else {**fallback, "status": "canceled"})


def handle_event(db: Session, event: dict) -> None:
    """Act on one verified event, exactly once. Commits.

    The ledger row goes in the same transaction as the effect: a duplicate
    hits the primary key and does nothing; a failure rolls both back so
    Stripe's retry does the work.
    """
    inserted = db.execute(
        pg_insert(StripeEvent)
        .values(event_id=event["id"], type=event["type"], processed_at=_now())
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(StripeEvent.event_id)
    ).first()
    if inserted is None:
        db.rollback()
        return

    kind = event["type"]
    obj = event["data"]["object"]
    if kind == "checkout.session.completed":
        if obj.get("subscription"):
            _apply_current(db, obj["subscription"], {"id": obj["subscription"]})
        _close_attempt(db, obj, ATTEMPT_COMPLETED)
    elif kind == "checkout.session.expired":
        _close_attempt(db, obj, ATTEMPT_EXPIRED)
    elif kind.startswith("customer.subscription."):
        _apply_current(db, obj["id"], obj)
    db.commit()


def current_subscription(db: Session, user: User) -> Subscription | None:
    """The subscription an account page should show: the live one if there is
    one (even past its grace -- that is exactly when the customer needs to
    see it), otherwise the most recently changed."""
    live = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status.in_(LIVE_STATUSES))
        .order_by(Subscription.updated_at.desc())
        .first()
    )
    if live is not None:
        return live
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.updated_at.desc())
        .first()
    )


def portal_url(db: Session, user: User) -> str:
    if not user.stripe_customer_id:
        raise BillingRefused(409, "There is no billing account to manage yet.")
    try:
        session = billing_stripe.create_portal_session(
            customer=user.stripe_customer_id, return_url=f"{config.site_url}/account"
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("could not open a Stripe portal session")
        raise BillingRefused(503, "Billing is unavailable right now. Please try again shortly.") from exc
    return session["url"]


@dataclasses.dataclass
class ReconcileResult:
    checked: int = 0
    corrected: int = 0


def _epoch(value: datetime.datetime | None) -> int | None:
    return int(value.timestamp()) if value else None


def _as_ended(row: Subscription, user: User) -> dict:
    """What a vanished subscription looks like: our own record, ended.

    Built from the row rather than blanks, so ending it keeps what it recorded
    -- amount and period -- instead of erasing them.
    """
    return {
        "id": row.stripe_subscription_id,
        "status": "canceled",
        "customer": user.stripe_customer_id,
        "metadata": {"user_id": str(row.user_id), "plan": row.plan, "founder": "true" if row.founder else "false"},
        "cancel_at": None,
        "cancel_at_period_end": False,
        "items": {
            "data": [
                {
                    "price": {"unit_amount": row.amount_pence},
                    "current_period_start": _epoch(row.current_period_start),
                    "current_period_end": _epoch(row.current_period_end),
                }
            ]
        },
    }


def reconcile(db: Session) -> ReconcileResult:
    """Bring every mirrored subscription into line with Stripe. Commits."""
    result = ReconcileResult()
    if not config.billing_enabled:
        return result

    seen: set[str] = set()
    for obj in billing_stripe.list_subscriptions():
        seen.add(obj["id"])
        result.checked += 1
        if apply_subscription(db, obj, source="reconcile"):
            result.corrected += 1

    stale = (
        db.query(Subscription)
        .filter(Subscription.status.in_(LIVE_STATUSES), Subscription.stripe_subscription_id.notin_(seen or {""}))
        .all()
    )
    for row in stale:
        result.checked += 1
        current = billing_stripe.retrieve_subscription(row.stripe_subscription_id)
        obj = current if current is not None else _as_ended(row, row.user)
        if apply_subscription(db, obj, source="reconcile"):
            result.corrected += 1

    db.query(CheckoutAttempt).filter(
        CheckoutAttempt.state == ATTEMPT_OPEN, CheckoutAttempt.expires_at <= _now()
    ).update({CheckoutAttempt.state: ATTEMPT_EXPIRED}, synchronize_session=False)
    db.commit()
    return result
