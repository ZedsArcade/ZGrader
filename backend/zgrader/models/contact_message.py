import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ContactTopic(str, enum.Enum):
    """Which side of the business the enquiry is about.

    `other` exists because forcing a choice between two brands on someone who
    doesn't yet know the difference produces mis-routed mail, not cleaner data.
    """

    lab = "lab"
    care = "care"
    other = "other"


class ContactMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An enquiry sent through the public contact form.

    Stored rather than only emailed, and that is the point of the table rather
    than an incidental convenience: SMTP is currently unconfigured (see the
    known-open list in AGENTS.md), so an email-only contact form would accept a
    customer's message, report success, and drop it. The row is the delivery
    guarantee; the email is a notification about a row that already exists.

    `notified` records which of the two actually happened, so the operator can
    find the messages they were never told about once SMTP is working.
    """

    __tablename__ = "contact_messages"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    topic: Mapped[ContactTopic] = mapped_column(
        Enum(ContactTopic, name="contact_topic"), default=ContactTopic.other, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Which language the form was in, so a reply can be written in the one they
    # wrote in rather than guessed from the text.
    language: Mapped[str] = mapped_column(String(5), default="en", nullable=False)

    # Optional: set when the enquiry is about a specific submission, which
    # saves the operator matching it up by hand. Deliberately *not* a foreign
    # key -- the sender need not be logged in, the code is typed by hand, and a
    # typo should not reject the message.
    submission_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # For abuse triage only. Same source as the rate limiter uses.
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    handled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
