"""add contact_messages table

Backs the public contact form. The table is the point rather than a log of one:
SMTP is unconfigured on this deployment, so an email-only form would accept an
enquiry, tell the sender it was sent, and drop it. The row is what makes the
form honest; the notification email is a convenience on top of it.

`notified` records whether that email actually went out, so once SMTP works the
operator can find the enquiries they were never told about instead of assuming
an empty inbox meant nobody wrote.

submission_code is deliberately a plain string and not a foreign key: the
sender need not have an account, types the code by hand, and a typo must not
reject the message.

Revision ID: b7f4c2e19a83
Revises: a1c47e93f2b8
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7f4c2e19a83"
down_revision = "a1c47e93f2b8"
branch_labels = None
depends_on = None

_TOPIC_NAME = "contact_topic"
_TOPIC_VALUES = ("lab", "care", "other")

#: The column's type. postgresql.ENUM rather than sa.Enum, and that matters:
#: `create_type` is a postgresql.ENUM parameter, and the generic sa.Enum
#: *accepts and silently ignores it*. This migration originally used
#: sa.Enum(..., create_type=False), which constructed without complaint and
#: then had create_table emit CREATE TYPE for the enum created a few lines
#: above, failing with
#:
#:     psycopg.errors.DuplicateObject: type "contact_topic" already exists
#:
#: Alembic runs a migration in one transaction, so the whole thing rolled back
#: -- leaving no table, no type, and alembic_version unmoved, which made it
#: look like the migration had never been attempted rather than that it had
#: failed. It reached production, where it stopped `migrate` completing and so
#: stopped `backend` and `worker` (which wait on service_completed_successfully)
#: from ever starting.
_TOPIC_COLUMN_TYPE = postgresql.ENUM(*_TOPIC_VALUES, name=_TOPIC_NAME, create_type=False)


def upgrade() -> None:
    # Created explicitly because the column type above is create_type=False,
    # and kept explicit rather than left to create_table so the downgrade can
    # be symmetrical -- dropping a table does not drop the enum it used.
    # checkfirst so a database left with the type from a partial earlier run
    # is repaired rather than rejected.
    postgresql.ENUM(*_TOPIC_VALUES, name=_TOPIC_NAME).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "contact_messages",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("topic", _TOPIC_COLUMN_TYPE, nullable=False, server_default="other"),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=5), nullable=False, server_default="en"),
        sa.Column("submission_code", sa.String(length=20), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("handled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # The operator's two working queries: newest first, and "what still needs
    # a reply". Both are cheap now and neither gets cheaper once the table has
    # a year of enquiries in it.
    op.create_index(
        "ix_contact_messages_created_at", "contact_messages", [sa.text("created_at DESC")]
    )
    op.create_index(
        "ix_contact_messages_unhandled",
        "contact_messages",
        [sa.text("created_at DESC")],
        postgresql_where=sa.text("handled = false"),
    )


def downgrade() -> None:
    # Dropping this destroys every enquiry that has not been answered yet, and
    # unlike most of this schema there is no other copy -- an unsent
    # notification email means the row is the only record. Export before
    # downgrading past this point.
    op.drop_index("ix_contact_messages_unhandled", table_name="contact_messages")
    op.drop_index("ix_contact_messages_created_at", table_name="contact_messages")
    op.drop_table("contact_messages")
    # After the table, because a type still in use cannot be dropped.
    postgresql.ENUM(name=_TOPIC_NAME).drop(op.get_bind(), checkfirst=True)
