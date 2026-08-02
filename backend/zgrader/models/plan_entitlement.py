"""What each plan is allowed to do, as data rather than code.

The free tier's cap and cooldown, and every paid plan's, are operator-tunable
from the admin panel -- pricing moves, and a limit that needs a deploy to
change is a limit that stays wrong. `zgrader.entitlements` is the only reader.

A NULL submission_limit means unlimited, which is how a subscription plan is
expressed. It is a real value here rather than a magic large number so the
"unlimited" case is unambiguous everywhere it is read.
"""

from sqlalchemy import CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

# The plan a user has when they hold no active subscription.
FREE_PLAN = "free"


class PlanEntitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plan_entitlements"

    # Matches Subscription.plan, which is a free-form string mirrored from the
    # payment provider. Unique so a plan can't end up with two conflicting
    # entitlement rows.
    plan: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # None = unlimited submissions.
    submission_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Length of the quota window, in days. The window is anchored per user
    # (see User.quota_period_started_at) rather than to a calendar boundary,
    # so nobody gets a one-day week by signing up on a Sunday.
    period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)

    __table_args__ = (
        CheckConstraint("submission_limit IS NULL OR submission_limit >= 0", name="ck_plan_limit_non_negative"),
        CheckConstraint("period_days >= 1", name="ck_plan_period_at_least_one_day"),
    )
