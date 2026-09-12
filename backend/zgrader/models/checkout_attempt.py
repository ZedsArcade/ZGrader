"""One row per Checkout session this server starts.

Three jobs in one row: it is the founder-seat hold while a customer is on
Stripe's page, the record of which Terms they accepted and when they consented
to start immediately, and the guard that turns a second Subscribe click (or a
second tab) into the same session rather than a second subscription.
"""

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

ATTEMPT_OPEN = "open"
ATTEMPT_COMPLETED = "completed"
ATTEMPT_EXPIRED = "expired"
# The Stripe call failed after the row was committed; releases any seat.
ATTEMPT_ABANDONED = "abandoned"


class CheckoutAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "checkout_attempts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(String(64), nullable=False)
    amount_pence: Mapped[int] = mapped_column(Integer, nullable=False)
    founder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    terms_version: Mapped[str] = mapped_column(String(20), nullable=False)
    consented_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    # Kept so a repeat request can be handed the open session without a
    # Stripe round trip.
    stripe_session_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Outlives the Stripe session (31 min) by two minutes, so a founder seat
    # is never released while its session could still complete.
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default=ATTEMPT_OPEN, server_default=ATTEMPT_OPEN)
