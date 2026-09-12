"""Every Stripe event this server has acted on, by Stripe's own id.

Written in the same transaction as the event's effect: a duplicate delivery
hits the primary key and does nothing, and a failed one rolls back with its
effect so Stripe's retry does the work for real.
"""

import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import utcnow


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
