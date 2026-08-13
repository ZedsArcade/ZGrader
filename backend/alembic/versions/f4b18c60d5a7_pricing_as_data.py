"""Move every published price into the database

The public pricing page quotes figures that are still a draft, so they cannot
live in the site copy: a price that needs a deploy to change is a price that
stays wrong, exactly as `plan_entitlements.submission_limit` already argues for
quota caps.

It also closes a divergence that was live until now. The copy said "the first
check is free" while the seeded free plan granted three a week -- two different
products described in two places, with nothing keeping them honest. With the
allowance and the price on the same row, and the page rendering from it, the
quote and the enforcement cannot drift apart.

Money is stored in whole pence. Floats are a rounding bug waiting for a total,
and nothing here needs sub-penny precision.

Revision ID: f4b18c60d5a7
Revises: e2f7b1a94c56
"""

import sqlalchemy as sa
from alembic import op

revision = "f4b18c60d5a7"
down_revision = "e2f7b1a94c56"
branch_labels = None
depends_on = None

# Loose figures that belong to no plan and no volume band. Nullable throughout:
# NULL means "do not show this offer", which is a different claim from zero.
_SETTINGS_COLUMNS = (
    "collection_triage_guide_pence",
    "founder_price_pence",
    "founder_seats",
    "subscriber_discount_pct",
)


def upgrade() -> None:
    op.add_column("plan_entitlements", sa.Column("price_pence", sa.Integer(), nullable=True))
    op.add_column("plan_entitlements", sa.Column("billing_period", sa.String(16), nullable=True))
    op.create_check_constraint(
        "ck_plan_price_non_negative", "plan_entitlements", "price_pence IS NULL OR price_pence >= 0"
    )

    op.create_table(
        "physical_price_tiers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("min_qty", sa.Integer(), nullable=False, unique=True),
        # NULL = the open-ended top band, "25 and up".
        sa.Column("max_qty", sa.Integer(), nullable=True),
        sa.Column("price_pence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("min_qty >= 1", name="ck_physical_tier_min_qty_at_least_one"),
        sa.CheckConstraint("max_qty IS NULL OR max_qty >= min_qty", name="ck_physical_tier_max_ge_min"),
        sa.CheckConstraint("price_pence >= 0", name="ck_physical_tier_price_non_negative"),
    )

    for column in _SETTINGS_COLUMNS:
        op.add_column("settings", sa.Column(column, sa.Integer(), nullable=True))

    # Retire the `tier1` placeholder.
    #
    # It was seeded before there was any pricing -- an unlimited plan with a
    # name that was never a product. The seeder only ever *adds* missing plans,
    # so on a database that already has it the row would survive and the new
    # public pricing page would render a card headed "tier1", unlimited, at £0.
    # A deployed database is exactly where that shows up and nowhere else,
    # which is why it is handled here rather than in the seed.
    #
    # Guarded on nothing referencing it. No code constructs a Subscription
    # today, so in practice this always fires -- but a plan with a live
    # subscriber is somebody's paid entitlement, and a migration should not
    # take that away on an assumption about the code that was true when it was
    # written.
    op.execute(
        """
        DELETE FROM plan_entitlements
        WHERE plan = 'tier1'
          AND NOT EXISTS (SELECT 1 FROM subscriptions WHERE subscriptions.plan = 'tier1')
        """
    )


def downgrade() -> None:
    # `tier1` is not recreated: whether it existed is not knowable from here,
    # and re-seeding restores it for anyone who genuinely wants it back.
    for column in _SETTINGS_COLUMNS:
        op.drop_column("settings", column)
    op.drop_table("physical_price_tiers")
    op.drop_constraint("ck_plan_price_non_negative", "plan_entitlements", type_="check")
    op.drop_column("plan_entitlements", "billing_period")
    op.drop_column("plan_entitlements", "price_pence")
