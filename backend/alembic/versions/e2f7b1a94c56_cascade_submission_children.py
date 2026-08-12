"""Delete a submission's children in the database, not in the ORM

Deleting a submission produced a 500 in production:

    ForeignKeyViolation: update or delete on table "submissions" violates
    foreign key constraint "analysis_results_submission_id_fkey"

Every FK pointing at `submissions` was ON DELETE NO ACTION, so the cascade
lived entirely in the SQLAlchemy relationships. That works only while nothing
else writes: the ORM loads the children, deletes them, then deletes the parent,
and anything inserting an `analysis_results` row between those two statements
strands it and the parent delete fails.

Something does write. `confirm-crop` runs the pipeline inside the API request,
and the worker runs it too -- driven by a watchdog on the scans directory and a
poll loop over submissions in `created`/`awaiting_scans`. Nothing serialises
the two, so a delete overlapping either one fails, and while a submission keeps
being re-picked up it fails *every* time, which is what the operator hit.

With ON DELETE CASCADE the child rows go in the same statement as the parent,
so there is no window to interleave with, and an insert that arrives after the
delete commits fails its own FK check -- which is the correct answer rather
than a stranded row.

`audit_logs` is the exception and gets SET NULL: the history of what happened
to a submission is worth keeping once the submission is gone, which is why
`delete_submission` already nulled it by hand.

This also retires a trap: deleting a submission in SQL used to mean deleting
five child tables first, in the right order, and nulling a sixth.

Revision ID: e2f7b1a94c56
Revises: d5e8a3c71b92
"""

from alembic import op

revision = "e2f7b1a94c56"
down_revision = "d5e8a3c71b92"
branch_labels = None
depends_on = None

# table -> column, for every FK that points at submissions.id.
_CASCADE_TABLES = (
    "cards",
    "scan_images",
    "analysis_results",
    "grading_company_comparisons",
    "reports",
)
_COLUMN = "submission_id"


def _constraint(table: str) -> str:
    """The name Postgres generates for these, and the one the production error
    quoted (`analysis_results_submission_id_fkey`)."""
    return f"{table}_{_COLUMN}_fkey"


def upgrade() -> None:
    for table in _CASCADE_TABLES:
        op.drop_constraint(_constraint(table), table, type_="foreignkey")
        op.create_foreign_key(
            _constraint(table),
            table,
            "submissions",
            [_COLUMN],
            ["id"],
            ondelete="CASCADE",
        )

    op.drop_constraint(_constraint("audit_logs"), "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        _constraint("audit_logs"),
        "audit_logs",
        "submissions",
        [_COLUMN],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    for table in (*_CASCADE_TABLES, "audit_logs"):
        op.drop_constraint(_constraint(table), table, type_="foreignkey")
        op.create_foreign_key(_constraint(table), table, "submissions", [_COLUMN], ["id"])
