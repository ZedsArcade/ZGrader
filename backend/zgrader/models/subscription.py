"""Billing state, mirrored from Stripe.

Written by exactly one function, zgrader.billing.apply_subscription -- the
webhook, the reconcile sweep and the admin button all call it, so the rules
for what Stripe's state means live in one place.

Deliberately holds no card data of any kind. With Stripe Checkout the card
number never touches this server, which is what keeps PCI scope at its
lightest (SAQ A). There should never be a column here for a card number,
expiry or CVV.
"""

import datetime
import enum
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionStatus(str, enum.Enum):
    """Stripe's subscription statuses. Vocabulary only: the column is a plain
    string, because Stripe adds statuses and adding a value to a Postgres enum
    in a migration is how b7f4c2e19a83 took the stack down. Compare with
    `.value`."""

    active = "active"
    trialing = "trialing"
    past_due = "past_due"
    canceled = "canceled"
    incomplete = "incomplete"
    incomplete_expired = "incomplete_expired"
    unpaid = "unpaid"
    paused = "paused"


#: Statuses in which a subscription is still running and billing. At most one
#: per user (the index below). Includes past_due even after the entitlement
#: grace has run out (see zgrader.entitlements): Stripe is still retrying, so
#: a second subscription would be a second bill.
LIVE_STATUSES: tuple[str, ...] = (
    SubscriptionStatus.active.value,
    SubscriptionStatus.trialing.value,
    SubscriptionStatus.past_due.value,
)

#: Never paid, so never counted as a founder seat.
NEVER_PAID_STATUSES: tuple[str, ...] = (
    SubscriptionStatus.incomplete.value,
    SubscriptionStatus.incomplete_expired.value,
)


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        # Declared here rather than in raw SQL so create_all (the test schema)
        # builds it too -- ix_users_email_lower is the cautionary tale.
        Index(
            "uq_subscriptions_one_live_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('active', 'trialing', 'past_due')"),
        ),
    )

    # ondelete matches the migration, so a schema built by create_all (the
    # test suite) behaves the same as one built by Alembic.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    plan: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    # Founder seat counting and the account badge.
    founder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # What this subscriber actually pays, read back from Stripe. Makes the
    # founder lock and any later price change visible per subscriber.
    amount_pence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Read from the subscription *item*: current API versions keep the period
    # there. current_period_start also anchors the past_due grace.
    current_period_start: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When a pending cancellation takes effect. Stripe signals it as cancel_at
    # (flexible billing mode) or cancel_at_period_end (classic); both land here.
    cancel_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("checkout_attempts.id", ondelete="SET NULL"), nullable=True
    )
    # Proof of what was agreed at purchase, copied from the checkout attempt.
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consented_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subscriptions")  # noqa: F821
