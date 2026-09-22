"""Charge a check when an analysis scores it, not when a submission is created

A check used to be spent at "Create submission", before any photo existed, so
abandoning at the upload step -- or a photo that never cropped -- still cost
one. It is now spent the first time an analysis gives the submission a score,
and `charged_at` records that it happened, which is what keeps a re-analysis
(a late back photo) from charging twice.

Every existing row is backfilled to its `created_at`: all of them were charged
at creation under the old rule, and NULL would read as "never charged".

`mail_in` marks a submission whose card is coming by post. It has no photos
for days by design, so the draft cap and the stale-draft sweep must not treat
it as abandoned.

`cards.card_name` becomes optional: the photo-first page asks for the photo
first and the name is a label the customer may add later.

Revision ID: 5c1e8f3a9b27
Revises: 9e3b5d1f7a24
"""

import sqlalchemy as sa
from alembic import op

revision = "5c1e8f3a9b27"
down_revision = "9e3b5d1f7a24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("charged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "submissions",
        sa.Column("mail_in", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE submissions SET charged_at = created_at")
    op.alter_column("cards", "card_name", existing_type=sa.String(200), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE cards SET card_name = 'Untitled card' WHERE card_name IS NULL")
    op.alter_column("cards", "card_name", existing_type=sa.String(200), nullable=False)
    op.drop_column("submissions", "mail_in")
    op.drop_column("submissions", "charged_at")
