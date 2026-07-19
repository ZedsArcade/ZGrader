import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=True
    )
    # Nullable: system-generated actions (e.g. auto-publish, pipeline errors)
    # have no human actor.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # One-directional (no back_populates) -- just for convenient joined
    # reads in the admin audit log view.
    submission: Mapped["Submission | None"] = relationship(  # noqa: F821
        foreign_keys=[submission_id], viewonly=True
    )
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id], viewonly=True)  # noqa: F821
