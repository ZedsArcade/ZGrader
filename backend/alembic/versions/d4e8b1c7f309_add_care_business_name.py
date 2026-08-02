"""add settings.care_business_name

The site now carries two public brands: the analysis/pre-grading side
(business_name) and the card-care/restoration side reached at /care. Both are
operator-editable so neither is baked into the frontend.

A server_default is set as well as the model default because this column is
NOT NULL and the settings row already exists in every deployed database --
without it the ALTER would fail on the existing row.

Revision ID: d4e8b1c7f309
Revises: b3d61f8a92c7
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e8b1c7f309"
down_revision = "b3d61f8a92c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column(
            "care_business_name",
            sa.String(length=200),
            nullable=False,
            server_default="GemCare",
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "care_business_name")
