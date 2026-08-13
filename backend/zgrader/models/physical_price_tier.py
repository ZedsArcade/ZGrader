"""Per-card prices for the in-hand pre-grading service, as a volume table.

Deliberately *not* more rows in `plan_entitlements`. That table is read by
`entitlements.active_plan()` to decide what an account may do, and a row named
after a physical service sitting in it is one typo away from granting somebody a
software plan. These are two different things that both happen to be called
"pricing", and keeping them apart is cheaper than remembering they are separate.

Nothing enforces these. They are quoted on the public pricing page and fulfilled
by hand -- there is no checkout, and physical work is arranged by enquiry.
"""

from sqlalchemy import CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PhysicalPriceTier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One band of the volume table, e.g. "2-9 cards, £10 each"."""

    __tablename__ = "physical_price_tiers"

    # Inclusive lower bound of the band.
    min_qty: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)

    # Inclusive upper bound, or NULL for the open-ended top band ("25+"). NULL
    # rather than a large sentinel so "and up" is unambiguous wherever it is
    # read, the same choice `submission_limit` makes for "unlimited".
    max_qty: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Price per card in this band, in whole pence -- £4.50 is 450. Integer for
    # the same reason as PlanEntitlement.price_pence.
    price_pence: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("min_qty >= 1", name="ck_physical_tier_min_qty_at_least_one"),
        CheckConstraint(
            "max_qty IS NULL OR max_qty >= min_qty", name="ck_physical_tier_max_ge_min"
        ),
        CheckConstraint("price_pence >= 0", name="ck_physical_tier_price_non_negative"),
    )
