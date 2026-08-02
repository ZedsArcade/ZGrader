"""add plan_entitlements table and per-user quota counters

Turns the free-tier cap described on the Services page into something actually
enforced, with the numbers editable from the admin panel rather than baked in.

users.quota_used is a counter rather than a derived COUNT(*) of submissions on
purpose: submissions can be deleted in any status, so deriving usage would
refund a credit on delete and let a spent quota be retried indefinitely.

Revision ID: e7a2c5d81b40
Revises: d4e8b1c7f309
"""

import sqlalchemy as sa
from alembic import op

revision = "e7a2c5d81b40"
down_revision = "d4e8b1c7f309"
branch_labels = None
depends_on = None

# Free gets a small weekly allowance; the first paid tier is unlimited, which
# is what NULL means here. Both are starting points -- the whole reason this is
# a table is that an operator can retune them without a deploy.
_SEED = (
    ("free", 3, 7),
    ("tier1", None, 7),
)


def upgrade() -> None:
    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plan", sa.String(length=64), nullable=False),
        sa.Column("submission_limit", sa.Integer(), nullable=True),
        sa.Column("period_days", sa.Integer(), nullable=False, server_default="7"),
        sa.CheckConstraint(
            "submission_limit IS NULL OR submission_limit >= 0",
            name="ck_plan_limit_non_negative",
        ),
        sa.CheckConstraint("period_days >= 1", name="ck_plan_period_at_least_one_day"),
    )
    op.create_index("ix_plan_entitlements_plan", "plan_entitlements", ["plan"], unique=True)

    for plan, limit, period_days in _SEED:
        op.execute(
            sa.text(
                "INSERT INTO plan_entitlements (id, created_at, updated_at, plan, "
                "submission_limit, period_days) VALUES (gen_random_uuid(), now(), now(), "
                ":plan, :limit, :period_days) ON CONFLICT (plan) DO NOTHING"
            ).bindparams(plan=plan, limit=limit, period_days=period_days)
        )

    op.add_column(
        "users",
        sa.Column("quota_period_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("quota_used", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "quota_used")
    op.drop_column("users", "quota_period_started_at")
    op.drop_index("ix_plan_entitlements_plan", table_name="plan_entitlements")
    op.drop_table("plan_entitlements")
