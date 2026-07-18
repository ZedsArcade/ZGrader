import enum

from sqlalchemy import Boolean, Enum, String
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

    submissions: Mapped[list["Submission"]] = relationship(  # noqa: F821
        back_populates="user", foreign_keys="Submission.user_id"
    )
