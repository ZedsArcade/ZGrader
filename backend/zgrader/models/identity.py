"""A third-party sign-in linked to an account.

Separate from `users` rather than a pair of columns on it, so an account can
hold several identities later without a schema change, and so the absence of
a row is the plain answer to "can this person sign in with Google?".

Deliberately holds no tokens. The provider's access and refresh tokens are
used once during callback to read the profile and then dropped -- nothing
here needs ongoing API access on the user's behalf, and storing them would
turn this table into a credential store worth attacking.
"""

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

GOOGLE = "google"


class Identity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "identities"

    user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    # The provider's own stable identifier for the person (Google's `sub`).
    # Matched on in preference to the email address, which a person can
    # change at the provider without becoming a different person.
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped["User"] = relationship(back_populates="identities")  # noqa: F821

    __table_args__ = (
        # One provider account maps to exactly one local account. Without
        # this, a race on first sign-in could produce two accounts for the
        # same Google user.
        UniqueConstraint("provider", "provider_user_id", name="uq_identity_provider_subject"),
    )
