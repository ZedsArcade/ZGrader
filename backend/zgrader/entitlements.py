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
from zgrader.models.subscription import Subscription, SubscriptionStatus

_ENTITLED_STATUSES = (SubscriptionStatus.active, SubscriptionStatus.trialing)

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


def active_plan(db: Session, user: User) -> str:
    """The plan this account is on -- its active subscription, or free."""
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.status.in_(_ENTITLED_STATUSES),
        )
        .first()
    )
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


def get_quota(db: Session, user: User) -> Quota:
    """The user's current quota, rolling the window forward if it has lapsed.

    Reading can mutate `user` (the rollover), which is intentional: the reset
    happens on next contact rather than needing a scheduled job.
    """
    plan = active_plan(db, user)
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
