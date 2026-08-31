"""Delete a user's children in the database, not in the ORM

The same fix as e2f7b1a94c56, one level up, and for the same reason.

Every FK pointing at `submissions` was given ON DELETE CASCADE there, but
`submissions.user_id` -- the FK pointing at *users* -- was left ON DELETE NO
ACTION, so account deletion still lived entirely in the SQLAlchemy
relationship: load the person's submissions, delete them one at a time, then
delete the user. That is the exact shape that reached production as a 500 on
submission delete, and the two writers named in that migration have not gone
away. `identities` and `subscriptions` already cascade; `submissions` was the
odd one out.

`audit_logs.user_id` and `reports.approved_by_user_id` get SET NULL rather
than CASCADE, matching how `audit_logs.submission_id` is already treated: the
record that something happened is worth keeping once the person is gone, and
the record of *who* is not. `delete_account` already nulls the audit rows by
hand, which works right up until a row is inserted between that UPDATE and the
DELETE; this makes the guarantee structural instead of a matter of timing.

Revision ID: c4f19b7e2d08
Revises: a8d47b1e6c30
"""

from alembic import op

revision = "c4f19b7e2d08"
down_revision = "a8d47b1e6c30"
branch_labels = None
depends_on = None

# table -> column, for the FKs pointing at users.id that outlive the person.
_SET_NULL = (
    ("audit_logs", "user_id"),
    ("reports", "approved_by_user_id"),
)


def _constraint(table: str, column: str) -> str:
    """The name Postgres generates for an unnamed FK, and the form the
    production error in e2f7b1a94c56 quoted."""
    return f"{table}_{column}_fkey"


def upgrade() -> None:
    op.drop_constraint(_constraint("submissions", "user_id"), "submissions", type_="foreignkey")
    op.create_foreign_key(
        _constraint("submissions", "user_id"),
        "submissions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    for table, column in _SET_NULL:
        op.drop_constraint(_constraint(table, column), table, type_="foreignkey")
        op.create_foreign_key(
            _constraint(table, column),
            table,
            "users",
            [column],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table, column in (("submissions", "user_id"), *_SET_NULL):
        op.drop_constraint(_constraint(table, column), table, type_="foreignkey")
        op.create_foreign_key(_constraint(table, column), table, "users", [column], ["id"])
