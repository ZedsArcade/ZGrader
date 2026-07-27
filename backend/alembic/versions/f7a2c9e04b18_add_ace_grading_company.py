"""add ACE to the grading_company enum

Revision ID: f7a2c9e04b18
Revises: e5c8b2a71d40
Create Date: 2026-07-26 00:00:00.000000

The enum backs both grading_company_tolerance_rules.company and
grading_company_comparisons.company, so the type has to know about ACE
before seed_tolerance_rules can insert its rows at startup.

PostgreSQL cannot remove a value from an enum, so the downgrade only clears
the ACE data -- see the note there.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f7a2c9e04b18'
down_revision: Union[str, None] = 'e5c8b2a71d40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS keeps this safe to re-run. Postgres 12+ allows ADD VALUE
    # inside a transaction as long as the new value isn't *used* in the same
    # one -- the ACE tolerance rows are inserted later, by startup seeding.
    op.execute("ALTER TYPE grading_company ADD VALUE IF NOT EXISTS 'ACE'")


def downgrade() -> None:
    # Postgres has no DROP VALUE for enums; recreating the type would mean
    # rewriting both dependent tables. Deleting the ACE rows leaves the schema
    # valid and the comparison back to four companies, which is the part that
    # actually matters -- the unused enum label is harmless.
    op.execute("DELETE FROM grading_company_comparisons WHERE company = 'ACE'")
    op.execute("DELETE FROM grading_company_tolerance_rules WHERE company = 'ACE'")
