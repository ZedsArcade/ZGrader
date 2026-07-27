"""Billing state, mirrored from the payment provider.

Nothing writes to this table yet -- it exists so the Stripe work has a
defined shape to land in rather than inventing one under time pressure, and
so entitlement checks have a single place to read from.

Deliberately holds no card data of any kind. With Stripe Checkout the card
number never touches this server, which is what keeps PCI scope at its
lightest (SAQ A). There should never be a column here for a card number,
expiry or CVV.
"""

import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SubscriptionStatus(str, enum.Enum):
    """Mirrors the Stripe subscription statuses that matter to us."""

    active = "active"
    trialing = "trialing"
    past_due = "past_due"
    canceled = "canceled"
    incomplete = "incomplete"


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    # ondelete matches the migration, so a schema built by create_all (the
    # test suite) behaves the same as one built by Alembic. The ORM-level
    # cascade on User.subscriptions covers deletion either way; this makes a
    # raw SQL delete safe too.
    user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Provider-side identifiers, so the local row can always be reconciled
    # against the source of truth.
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    plan: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"), nullable=False
    )
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="subscriptions")  # noqa: F821
