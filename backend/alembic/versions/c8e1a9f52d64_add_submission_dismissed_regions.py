"""add submissions.dismissed_regions

Revision ID: c8e1a9f52d64
Revises: b7d3c1f04e28
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c8e1a9f52d64'
down_revision: Union[str, None] = 'b7d3c1f04e28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('submissions', sa.Column('dismissed_regions', postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('submissions', 'dismissed_regions')
