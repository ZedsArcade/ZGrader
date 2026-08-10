"""issue submission codes from a sequence instead of COUNT(*) + 1

COUNT(*) + 1 handed the same code out twice. Deleting a submission lowered the
count, so the next one reused a code that had already existed -- a
unique-constraint 500 if a row still held it, and worse if none did: the scans
and reports directories are named after the code and are NOT removed by a
database delete, so a new customer's submission lands in a directory belonging
to someone else's.

That is not hypothetical. On this deployment nine test submissions were
deleted, three of their directories survived the purge because they were owned
by an earlier APP_UID, the counter restarted at SUB-00001, and the first real
analysis died with PermissionError writing front_base.png into a directory it
did not own.

The sequence is seeded past every code ever *issued*, not merely those still
present. Codes of deleted submissions are recoverable from audit_logs, where
delete_submission records {"deleted_code": ...} precisely so the history
survives the row -- which is what makes it possible to avoid reissuing them
here.

Revision ID: c9a3e15b7d24
Revises: b7f4c2e19a83
"""

import sqlalchemy as sa
from alembic import op

revision = "c9a3e15b7d24"
down_revision = "b7f4c2e19a83"
branch_labels = None
depends_on = None

_SEQUENCE = "submission_code_seq"

# Highest number ever handed out: live submissions, plus the codes of deleted
# ones recorded in the audit log. regexp_replace strips the "SUB-" so a later
# change to the prefix cannot break this, and NULLIF guards a detail row whose
# deleted_code is absent or non-numeric rather than failing the cast.
_HIGHEST_ISSUED = sa.text(
    """
    SELECT COALESCE(MAX(number), 0) FROM (
        SELECT NULLIF(regexp_replace(submission_code, '\\D', '', 'g'), '')::bigint AS number
        FROM submissions
        UNION ALL
        SELECT NULLIF(regexp_replace(detail->>'deleted_code', '\\D', '', 'g'), '')::bigint
        FROM audit_logs
        WHERE action = 'submission_deleted'
    ) AS issued
    """
)


def upgrade() -> None:
    connection = op.get_bind()
    op.execute(sa.schema.CreateSequence(sa.Sequence(_SEQUENCE), if_not_exists=True))

    highest = connection.execute(_HIGHEST_ISSUED).scalar() or 0
    # is_called=false so the next nextval() returns exactly this value rather
    # than one past it -- setval's third argument is the difference between
    # "the last value used" and "the next value to use", and getting it wrong
    # silently skips a code.
    connection.execute(
        sa.text("SELECT setval(:name, :value, false)"),
        {"name": _SEQUENCE, "value": highest + 1},
    )


def downgrade() -> None:
    # Dropping the sequence returns code allocation to COUNT(*) + 1 and with it
    # the reuse bug. Nothing else depends on it, so this is safe in the
    # mechanical sense and unwise in every other one.
    op.execute(sa.schema.DropSequence(sa.Sequence(_SEQUENCE), if_exists=True))
