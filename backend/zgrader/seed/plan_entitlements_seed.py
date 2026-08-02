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

_PLANS: tuple[tuple[str, int | None, int], ...] = (
    # (plan, submission_limit, period_days).  None = unlimited.
    ("free", 3, 7),
    ("tier1", None, 7),
)


def seed_plan_entitlements(db: Session) -> None:
    existing = {row.plan for row in db.query(PlanEntitlement.plan).all()}
    added = False
    for plan, submission_limit, period_days in _PLANS:
        if plan in existing:
            continue
        db.add(
            PlanEntitlement(
                plan=plan,
                submission_limit=submission_limit,
                period_days=period_days,
            )
        )
        added = True
    if added:
        db.commit()
