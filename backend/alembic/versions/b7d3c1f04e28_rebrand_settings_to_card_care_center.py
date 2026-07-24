"""rebrand settings business_name/disclaimer to Card Care Center

Revision ID: b7d3c1f04e28
Revises: a19f7c2e5b3d
Create Date: 2026-07-24 00:00:00.000000

The Settings singleton is only ever inserted (seed_settings_singleton),
never updated, so a row seeded before the "ZGrader" -> "Card Care Center"
rebrand still carries the old name -- which is what the portal header
fetches and displays. This data migration updates the stale default in
place. It is scoped to the exact old value so it never clobbers an
operator's deliberately customised business name.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b7d3c1f04e28'
down_revision: Union[str, None] = 'a19f7c2e5b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE settings SET business_name = 'Card Care Center' "
        "WHERE business_name = 'ZGrader'"
    )
    op.execute(
        "UPDATE settings "
        "SET disclaimer_text = REPLACE(disclaimer_text, 'ZGrader', 'Card Care Center') "
        "WHERE disclaimer_text LIKE '%ZGrader%'"
    )


def downgrade() -> None:
    # Data-only migration -- not structurally reversible, and reverting the
    # name would just re-introduce the stale brand. Intentional no-op.
    pass
