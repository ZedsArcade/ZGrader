"""Stripe billing: string status, checkout attempts, event ledger

The subscription status becomes a plain string. Stripe has statuses the enum
never had (unpaid, incomplete_expired, paused), and adding values to a
Postgres enum in a migration is the trap b7f4c2e19a83 fell into -- a string
column with an allow-list in code has no such failure mode.

Nothing has ever written a subscriptions row (no code constructed one before
this release), so the conversion moves no real data; it is written to be
correct if it did.

Revision ID: 9e3b5d1f7a24
Revises: c4f19b7e2d08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "9e3b5d1f7a24"
down_revision = "c4f19b7e2d08"
branch_labels = None
depends_on = None

_OLD_STATUSES = ("active", "trialing", "past_due", "canceled", "incomplete")


def upgrade() -> None:
    op.alter_column(
        "subscriptions",
        "status",
        type_=sa.String(32),
        postgresql_using="status::text",
        existing_nullable=False,
    )
    op.execute("DROP TYPE IF EXISTS subscription_status")

    op.create_table(
        "checkout_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.String(64), nullable=False),
        sa.Column("amount_pence", sa.Integer(), nullable=False),
        sa.Column("founder", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("terms_version", sa.String(20), nullable=False),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=True, unique=True),
        sa.Column("stripe_session_url", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_checkout_attempts_user_id", "checkout_attempts", ["user_id"])

    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column("subscriptions", sa.Column("founder", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("subscriptions", sa.Column("amount_pence", sa.Integer(), nullable=True))
    op.add_column("subscriptions", sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("cancel_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("subscriptions", sa.Column("checkout_attempt_id", sa.Uuid(), nullable=True))
    op.add_column("subscriptions", sa.Column("terms_version", sa.String(20), nullable=True))
    op.add_column("subscriptions", sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        "fk_subscriptions_checkout_attempt_id",
        "subscriptions",
        "checkout_attempts",
        ["checkout_attempt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "uq_subscriptions_one_live_per_user",
        "subscriptions",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'trialing', 'past_due')"),
    )

    op.add_column("users", sa.Column("quota_plan", sa.String(64), nullable=True))
    op.add_column("plan_entitlements", sa.Column("stripe_product_id", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_plan_entitlements_stripe_product_id", "plan_entitlements", ["stripe_product_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_plan_entitlements_stripe_product_id", "plan_entitlements", type_="unique")
    op.drop_column("plan_entitlements", "stripe_product_id")
    op.drop_column("users", "quota_plan")

    op.drop_index("uq_subscriptions_one_live_per_user", table_name="subscriptions")
    op.drop_constraint("fk_subscriptions_checkout_attempt_id", "subscriptions", type_="foreignkey")
    for column in (
        "consented_at",
        "terms_version",
        "checkout_attempt_id",
        "cancel_at",
        "current_period_start",
        "amount_pence",
        "founder",
    ):
        op.drop_column("subscriptions", column)

    op.drop_table("stripe_events")
    op.drop_index("ix_checkout_attempts_user_id", table_name="checkout_attempts")
    op.drop_table("checkout_attempts")

    # Statuses the old enum cannot hold collapse to canceled -- the one old
    # value that grants nothing.
    listed = ", ".join(f"'{s}'" for s in _OLD_STATUSES)
    op.execute(f"UPDATE subscriptions SET status = 'canceled' WHERE status NOT IN ({listed})")
    # postgresql.ENUM, not sa.Enum: only the dialect type honours create_type.
    postgresql.ENUM(*_OLD_STATUSES, name="subscription_status").create(op.get_bind(), checkfirst=True)
    op.alter_column(
        "subscriptions",
        "status",
        type_=postgresql.ENUM(*_OLD_STATUSES, name="subscription_status", create_type=False),
        postgresql_using="status::subscription_status",
        existing_nullable=False,
    )
