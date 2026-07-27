"""add settings contact + social fields

Revision ID: d4b1e7a0c395
Revises: c8e1a9f52d64
Create Date: 2026-07-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4b1e7a0c395'
down_revision: Union[str, None] = 'c8e1a9f52d64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('settings', sa.Column('contact_email', sa.String(length=320), nullable=True))
    op.add_column('settings', sa.Column('contact_location', sa.String(length=200), nullable=True))
    op.add_column('settings', sa.Column('contact_response_days', sa.Integer(), nullable=True))
    op.add_column(
        'settings',
        sa.Column('contact_in_person', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('settings', sa.Column('social_instagram', sa.String(length=500), nullable=True))
    op.add_column('settings', sa.Column('social_facebook', sa.String(length=500), nullable=True))
    op.add_column('settings', sa.Column('social_x', sa.String(length=500), nullable=True))
    op.add_column('settings', sa.Column('social_whatsapp', sa.String(length=32), nullable=True))

    # Seed the service area on the existing singleton row so the contact page
    # says something useful before the operator opens the settings form.
    op.execute("UPDATE settings SET contact_location = 'Gibraltar' WHERE contact_location IS NULL")


def downgrade() -> None:
    op.drop_column('settings', 'social_whatsapp')
    op.drop_column('settings', 'social_x')
    op.drop_column('settings', 'social_facebook')
    op.drop_column('settings', 'social_instagram')
    op.drop_column('settings', 'contact_in_person')
    op.drop_column('settings', 'contact_response_days')
    op.drop_column('settings', 'contact_location')
    op.drop_column('settings', 'contact_email')
