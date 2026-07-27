"""name ACE in the stored report disclaimer

Revision ID: e5c8b2a71d40
Revises: d4b1e7a0c395
Create Date: 2026-07-26 00:00:00.000000

settings.disclaimer_text is printed on every generated report and is only
ever inserted from the column default, never updated -- so a row seeded
before ACE was added to that default still lists only PSA/BGS/CGC/TAG.

The UPDATE is scoped to rows that still contain the exact un-amended
company list, so an operator who has rewritten their disclaimer keeps it.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5c8b2a71d40'
down_revision: Union[str, None] = 'd4b1e7a0c395'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = 'CGC, TAG, or any other third-party'
_NEW = 'CGC, TAG, ACE, or any other third-party'


def upgrade() -> None:
    op.execute(
        "UPDATE settings "
        f"SET disclaimer_text = REPLACE(disclaimer_text, '{_OLD}', '{_NEW}') "
        f"WHERE disclaimer_text LIKE '%{_OLD}%'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE settings "
        f"SET disclaimer_text = REPLACE(disclaimer_text, '{_NEW}', '{_OLD}') "
        f"WHERE disclaimer_text LIKE '%{_NEW}%'"
    )
