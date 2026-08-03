"""add identities table and make users.hashed_password nullable

Google sign-in. An account created that way has no password and never had
one, so the column has to allow NULL -- every read of it now copes with that,
notably the login path, which must still burn a password comparison rather
than answering fast and revealing the address exists.

Revision ID: f3b9d0c4a71e
Revises: e7a2c5d81b40
"""

import sqlalchemy as sa
from alembic import op

revision = "f3b9d0c4a71e"
down_revision = "e7a2c5d81b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "identities",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        # One provider account maps to exactly one local account; without this
        # a race on first sign-in could produce two accounts for one person.
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_identity_provider_subject"),
    )
    op.create_index("ix_identities_user_id", "identities", ["user_id"])

    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    # Accounts that only ever signed in with Google have no password to
    # restore, so the column cannot simply be made NOT NULL again -- they are
    # removed first. Destructive, and deliberately explicit about it.
    op.execute(
        "DELETE FROM users WHERE hashed_password IS NULL"
    )
    op.alter_column("users", "hashed_password", existing_type=sa.String(length=255), nullable=False)
    op.drop_index("ix_identities_user_id", table_name="identities")
    op.drop_table("identities")
