import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Card(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cards"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), unique=True, nullable=False
    )
    # References CardDimensionReference.game (a string key, not an FK id,
    # so seed data and migrations don't need to coordinate surrogate keys).
    game: Mapped[str] = mapped_column(String(100), nullable=False)
    set_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    card_name: Mapped[str] = mapped_column(String(200), nullable=False)
    card_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    foil: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission: Mapped["Submission"] = relationship(back_populates="card")  # noqa: F821
