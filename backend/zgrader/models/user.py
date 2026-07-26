import datetime
import enum

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    client = "client"
    operator = "operator"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.client, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    verification_token_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    password_reset_token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    password_reset_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Bumped whenever a password changes. It's a claim in every token, so
    # raising it invalidates every session that user has open -- which is what
    # makes a password reset actually remediate a compromise, given there's no
    # server-side session store to clear.
    token_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Proof of what was agreed and when. Needed to enforce the terms against
    # someone who says they never saw them.
    terms_accepted_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terms_version: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Kept separate from the transactional emails, which need no consent.
    # Nothing sends marketing today; this exists so consent is recordable
    # before anything does.
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Set when the user first checks out. Card details never reach this
    # server -- this is only Stripe's handle for them.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    # delete-orphan so closing an account removes the person's submissions
    # rather than trying to orphan them -- Submission.user_id is NOT NULL, so
    # without this a deletion fails outright.
    submissions: Mapped[list["Submission"]] = relationship(  # noqa: F821
        back_populates="user",
        foreign_keys="Submission.user_id",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
