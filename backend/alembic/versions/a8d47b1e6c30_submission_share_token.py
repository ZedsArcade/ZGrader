"""Give a submission a shareable public token

A customer sharing a report is the main way anyone new finds this service, so a
report needs a URL that can be handed to a stranger. `submission_code` cannot be
that URL: it comes from `submission_code_seq`, so codes are sequential and
guessable, and a public route keyed on one would let anybody walk the sequence
and read every customer's report. The code stays operator-facing.

So sharing runs on a separate secret. NULL means not shared, which is where
every submission starts and where it stays until someone opts in. Rotating the
token revokes whatever link is already out there; clearing it turns sharing off.

The unique index is partial. Most submissions are never shared, and there is no
reason to carry them in the index that resolves a public URL -- Postgres already
permits many NULLs under a plain unique index, so this is about keeping the index
small rather than about correctness. It is also declared on the model, not only
here, so `create_all` gives the test database the same constraint production has.

Revision ID: a8d47b1e6c30
Revises: f4b18c60d5a7
"""

import sqlalchemy as sa
from alembic import op

revision = "a8d47b1e6c30"
down_revision = "f4b18c60d5a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("share_token", sa.String(64), nullable=True))
    op.add_column(
        "submissions", sa.Column("share_enabled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_submissions_share_token",
        "submissions",
        ["share_token"],
        unique=True,
        postgresql_where=sa.text("share_token IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_submissions_share_token", table_name="submissions")
    op.drop_column("submissions", "share_enabled_at")
    op.drop_column("submissions", "share_token")
