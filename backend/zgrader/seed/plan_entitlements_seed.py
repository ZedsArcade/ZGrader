"""Seed data for PlanEntitlement -- the per-plan submission caps.

Starting points, not settled pricing: the entire reason these live in a table
is that an operator can retune them from the admin panel without a deploy. The
free tier gets a small weekly allowance; the first paid tier is unlimited,
which is what a NULL submission_limit means.

Upserts on `plan`, so re-seeding never clobbers a number an operator has
already tuned -- it only fills in plans that are missing.
"""

from sqlalchemy.orm import Session

from zgrader.models.plan_entitlement import PlanEntitlement

# (plan, submission_limit, period_days, price_pence, billing_period).
# A None limit means unlimited; a None price means the plan is not sold.
#
# The draft pricing at the time of writing.
#
# `pack` is display-only. "25 checks that never expire" is a persistent balance,
# and this table only does "N per rolling window", so there is nothing here that
# expresses it. A year is the closest honest approximation and matches how the
# offer is described ("buy once, use over a year"); it is also inside the 365
# cap the admin update schema enforces, so it stays editable.
#
# It costs nothing today because no code creates a Subscription, so nobody can
# be on this plan. The pack needs a real balance before it is sold through the
# app rather than by hand.
_PLANS: tuple[tuple[str, int | None, int, int | None, str | None], ...] = (
    ("free", 3, 7, None, None),
    ("pack", 25, 365, 400, "once"),
    ("monthly", 100, 30, 500, "month"),
    ("annual", 100, 30, 4000, "year"),
)


def seed_plan_entitlements(db: Session) -> None:
    existing = {row.plan for row in db.query(PlanEntitlement.plan).all()}
    added = False
    for plan, submission_limit, period_days, price_pence, billing_period in _PLANS:
        if plan in existing:
            continue
        db.add(
            PlanEntitlement(
                plan=plan,
                submission_limit=submission_limit,
                period_days=period_days,
                price_pence=price_pence,
                billing_period=billing_period,
            )
        )
        added = True
    if added:
        db.commit()
