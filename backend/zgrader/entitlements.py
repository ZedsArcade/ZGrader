"""What a given account is allowed to do.

One place for the question "can this user run another check?", so a change in
plan rules lands here and nowhere else.

The rules themselves are data (`plan_entitlements`), editable from the admin
panel, because pricing moves and a cap that needs a deploy to change is a cap
that stays wrong.

Two properties are deliberate and worth not undoing:

**Usage is counted, not derived.** `User.quota_used` is incremented when a
submission is created and never decremented. The obvious alternative -- count
the user's submission rows -- refunds a credit the moment someone deletes a
submission, and since deletion is allowed in any status that turns a spent
quota into unlimited retries.

**The window is anchored per user**, not to a calendar boundary, so it starts
when someone actually starts using the service rather than handing a Sunday
signup a one-day week. It advances in whole periods, so `resets_at` is a fixed
point that can be counted down to rather than a moving target.
"""

import dataclasses
import datetime

from sqlalchemy.orm import Session

from zgrader.models import User
from zgrader.models.plan_entitlement import FREE_PLAN, PlanEntitlement
from zgrader.models.subscription import LIVE_STATUSES, Subscription, SubscriptionStatus

#: How long a failed renewal keeps paid access while Stripe retries. Bounded
#: here rather than trusted to the Dashboard: Stripe's "when retries run out"
#: is a setting, and left at "leave it past due" an unbounded rule would grant
#: access forever. The go-live checklist still sets it to cancel.
PAST_DUE_GRACE = datetime.timedelta(days=21)

# Used only when the plan_entitlements row is missing entirely (an unseeded or
# partially-migrated database). Chosen to fail closed-but-usable: a small free
# allowance rather than either locking everyone out or handing out unlimited
# checks because a seed didn't run.
_FALLBACK_LIMIT = 3
_FALLBACK_PERIOD_DAYS = 7


@dataclasses.dataclass(frozen=True)
class Quota:
    """A user's current standing, as shown in the UI and enforced on create."""

    plan: str
    limit: int | None  # None = unlimited
    used: int
    period_days: int
    resets_at: datetime.datetime | None  # None when unlimited

    @property
    def unlimited(self) -> bool:
        return self.limit is None

    @property
    def remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(0, self.limit - self.used)

    @property
    def can_submit(self) -> bool:
        return self.limit is None or self.used < self.limit


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _aware(value: datetime.datetime) -> datetime.datetime:
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def is_entitled(sub: Subscription, now: datetime.datetime) -> bool:
    """Whether this subscription grants its plan right now.

    past_due counts from current_period_start -- the renewal that failed. By
    the time a renewal fails Stripe has already advanced the subscription into
    the new period, so current_period_end is a whole period away.
    """
    if sub.status in (SubscriptionStatus.active.value, SubscriptionStatus.trialing.value):
        return True
    if sub.status == SubscriptionStatus.past_due.value and sub.current_period_start is not None:
        return now < _aware(sub.current_period_start) + PAST_DUE_GRACE
    return False


def entitled_subscription(db: Session, user: User, now: datetime.datetime | None = None) -> Subscription | None:
    now = now or _now()
    live = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.status.in_(LIVE_STATUSES))
        .all()
    )
    return next((sub for sub in live if is_entitled(sub, now)), None)


def active_plan(db: Session, user: User) -> str:
    """The plan this account is on -- its entitled subscription, or free."""
    subscription = entitled_subscription(db, user)
    return subscription.plan if subscription else FREE_PLAN


def has_active_subscription(db: Session, user: User) -> bool:
    return active_plan(db, user) != FREE_PLAN


def _plan_rules(db: Session, plan: str) -> tuple[int | None, int]:
    """(submission_limit, period_days) for a plan, falling back if unseeded."""
    row = db.query(PlanEntitlement).filter(PlanEntitlement.plan == plan).first()
    if row is None and plan != FREE_PLAN:
        # An unknown plan name -- e.g. a new Stripe price nobody has configured
        # here yet -- must not silently grant unlimited access. Fall back to
        # the free tier's rules until an operator sets it up.
        row = db.query(PlanEntitlement).filter(PlanEntitlement.plan == FREE_PLAN).first()
    if row is None:
        return _FALLBACK_LIMIT, _FALLBACK_PERIOD_DAYS
    return row.submission_limit, row.period_days


def _roll_period_forward(user: User, period: datetime.timedelta, now: datetime.datetime) -> None:
    """Advance the user's window to the one containing `now`, resetting usage.

    Advances in whole periods rather than resetting the anchor to `now`, so the
    reset time stays on a stable cadence instead of drifting later with every
    visit. Mutates `user`; the caller owns the flush.
    """
    anchor = user.quota_period_started_at
    if anchor is None:
        return
    # Postgres returns tz-aware values, but a SQLite/naive round-trip in a test
    # would otherwise raise on the comparison below.
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=datetime.timezone.utc)
    if now < anchor + period:
        return
    whole_periods = (now - anchor) // period
    user.quota_period_started_at = anchor + whole_periods * period
    user.quota_used = 0


def _reset_if_plan_changed(user: User, plan: str) -> None:
    """A window belongs to the plan it was counted under.

    Derived on read rather than performed by whatever changed the plan, so
    every route is covered -- a webhook, reconcile, an operator, or a grace
    period simply running out with nobody writing anything. Mutates `user`;
    the caller owns the flush, same as the rollover below.
    """
    if (user.quota_plan or FREE_PLAN) == plan:
        return
    user.quota_used = 0
    user.quota_period_started_at = None
    user.quota_plan = plan


def get_quota(db: Session, user: User) -> Quota:
    """The user's current quota, rolling the window forward if it has lapsed.

    Reading can mutate `user` (the rollover), which is intentional: the reset
    happens on next contact rather than needing a scheduled job.
    """
    plan = active_plan(db, user)
    _reset_if_plan_changed(user, plan)
    limit, period_days = _plan_rules(db, plan)

    if limit is None:
        return Quota(plan=plan, limit=None, used=0, period_days=period_days, resets_at=None)

    period = datetime.timedelta(days=period_days)
    _roll_period_forward(user, period, _now())

    anchor = user.quota_period_started_at
    if anchor is not None and anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=datetime.timezone.utc)
    # Before the first submission there is no window yet, so nothing is
    # counting down -- the full allowance is simply available.
    resets_at = (anchor + period) if anchor is not None else None
    return Quota(
        plan=plan,
        limit=limit,
        used=user.quota_used,
        period_days=period_days,
        resets_at=resets_at,
    )


def can_create_submission(db: Session, user: User) -> bool:
    return get_quota(db, user).can_submit


def consume_submission(db: Session, user: User) -> None:
    """Spend one credit. Call once per submission actually created.

    Unlimited plans are a no-op, so the counter stays at zero rather than
    accumulating a number nothing reads -- and if a subscription later lapses,
    the free window starts clean instead of already spent.
    """
    quota = get_quota(db, user)
    if quota.unlimited:
        return
    if user.quota_period_started_at is None:
        # First ever submission starts the window.
        user.quota_period_started_at = _now()
        user.quota_used = 0
    user.quota_used += 1
    db.flush()
