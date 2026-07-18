from sqlalchemy import Boolean, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CardDimensionReference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-game physical card dimensions used to convert pixel measurements
    to millimeters during centering analysis.

    All dimension lookups in the analysis pipeline go through this table --
    never hardcode a game's size in Python. Adding a new supported game is a
    new row here, not a code change.
    """

    __tablename__ = "card_dimension_references"

    game: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    width_mm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    height_mm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    # False for games whose dimensions were assumed-standard rather than
    # confirmed against a physical card -- surfaced as a caveat in reports.
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
