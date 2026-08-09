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

revision = "b7f4c2e19a83"
down_revision = "a1c47e93f2b8"
branch_labels = None
depends_on = None

_TOPIC = sa.Enum("lab", "care", "other", name="contact_topic")


def upgrade() -> None:
    # create_type=False on the column below would leave this to the table
    # create; naming it explicitly instead keeps the downgrade symmetrical,
    # since a dropped table does not drop the enum type it used.
    _TOPIC.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "contact_messages",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "topic",
            sa.Enum("lab", "care", "other", name="contact_topic", create_type=False),
            nullable=False,
            server_default="other",
        ),
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
    _TOPIC.drop(op.get_bind(), checkfirst=True)
