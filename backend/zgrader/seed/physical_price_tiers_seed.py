"""Seed data for the in-hand pre-grading volume table.

Starting points, not settled pricing -- the whole reason these live in a table
is that the operator retunes them from the admin panel without a deploy.

Upserts on `min_qty`, so re-seeding never clobbers a price already tuned; it
only fills in bands that are missing.
"""

from sqlalchemy.orm import Session

from zgrader.models.physical_price_tier import PhysicalPriceTier

# (min_qty, max_qty, price_pence per card). None max = "and up".
#
# Note the step from the 2-9 band to 10-24: nine cards costs more in total than
# ten do. That is deliberate in the draft -- it pushes toward larger batches --
# but it means a quote built from these bands should charge the cheaper of "this
# band" and "the next band's minimum", or a customer ordering nine pays £90 for
# work that costs £70 at ten.
_TIERS: tuple[tuple[int, int | None, int], ...] = (
    (1, 1, 1500),
    (2, 9, 1000),
    (10, 24, 700),
    (25, None, 450),
)


def seed_physical_price_tiers(db: Session) -> None:
    existing = {row.min_qty for row in db.query(PhysicalPriceTier.min_qty).all()}
    added = False
    for min_qty, max_qty, price_pence in _TIERS:
        if min_qty in existing:
            continue
        db.add(
            PhysicalPriceTier(min_qty=min_qty, max_qty=max_qty, price_pence=price_pence)
        )
        added = True
    if added:
        db.commit()
