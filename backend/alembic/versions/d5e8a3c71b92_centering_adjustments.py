"""let a client nudge the centering lines, within an operator-set limit

Two columns, and they are deliberately separate concerns.

submissions.centering_adjustments holds the border widths a client moved,
beside the measurement rather than over it -- exactly as dismissed_regions
does. The per-side AnalysisResult stays the record of what was actually
measured, the combined score is derived from both, and clearing the column
restores the detected figures with no other trace.

settings.centering_adjust_limit_mm caps how far a line may move. It is a
setting rather than a constant because the right value is a judgement about
trust, not a measurement: it trades "let someone fix a line the border
detector placed wrongly" against "let someone dial in a better ratio on a
report they may show a buyer". Zero disables adjustment entirely, which is the
lever to reach for if it is ever abused -- no deploy, and nothing already
stored breaks.

Revision ID: d5e8a3c71b92
Revises: c9a3e15b7d24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "d5e8a3c71b92"
down_revision = "c9a3e15b7d24"
branch_labels = None
depends_on = None

#: The shipped cap, in millimetres. A card's printed border is only a few
#: millimetres wide, so this is a meaningful limit rather than a nominal one.
_DEFAULT_LIMIT_MM = "4.0"


def upgrade() -> None:
    op.add_column("submissions", sa.Column("centering_adjustments", JSONB(), nullable=True))
    op.add_column(
        "settings",
        sa.Column(
            "centering_adjust_limit_mm",
            sa.Numeric(4, 1),
            nullable=False,
            server_default=_DEFAULT_LIMIT_MM,
        ),
    )


def downgrade() -> None:
    # Dropping centering_adjustments discards every client adjustment. The
    # per-side measurements are untouched by design, so the scores revert to
    # what the pipeline detected rather than being lost -- but the record that
    # a client disagreed with a line goes, and with it the reason a published
    # report was marked adjusted.
    op.drop_column("settings", "centering_adjust_limit_mm")
    op.drop_column("submissions", "centering_adjustments")
