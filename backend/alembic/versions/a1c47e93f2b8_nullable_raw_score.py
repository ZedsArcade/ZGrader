"""allow analysis_results.raw_score to be NULL

NULL means unmeasurable -- the pipeline looked and could not tell. That is a
different answer from "we looked and it is bad", and while the column was NOT
NULL the two collapsed into a low score. The column was the reason the honest
answer could not be expressed.

Nothing emits NULL yet; this only makes it possible. Categories start
declining to score in a follow-up, so the schema change and the behaviour
change can be reviewed apart.

Revision ID: a1c47e93f2b8
Revises: f3b9d0c4a71e
"""

import sqlalchemy as sa
from alembic import op

revision = "a1c47e93f2b8"
down_revision = "f3b9d0c4a71e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "analysis_results", "raw_score", existing_type=sa.Numeric(4, 2), nullable=True
    )


def downgrade() -> None:
    # Rows with no score cannot be represented once the column is NOT NULL
    # again. Deleting them would silently drop a submission's analysis, so
    # they are given the lowest score instead -- wrong, but visibly wrong,
    # and recoverable by re-running the analysis. Downgrading past this point
    # therefore reintroduces exactly the confident-wrongness the column change
    # was made to remove; do it knowingly.
    op.execute("UPDATE analysis_results SET raw_score = 0 WHERE raw_score IS NULL")
    op.alter_column(
        "analysis_results", "raw_score", existing_type=sa.Numeric(4, 2), nullable=False
    )
