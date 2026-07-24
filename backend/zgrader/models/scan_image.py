import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ScanSide(str, enum.Enum):
    front = "front"
    back = "back"


class ScanImage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scan_images"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False
    )
    side: Mapped[ScanSide] = mapped_column(Enum(ScanSide, name="scan_side"), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    dpi: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    # 4 [x, y] pixel points (TL/TR/BR/BL) in this scan's own raw-image
    # coordinate space. NULL means "uploaded but not yet confirmed" --
    # self-serve uploads start NULL and only get analyzed once a human (or
    # auto-detection, for operator-dropped scans) sets this. See
    # zgrader.worker.watcher._confirmed_sides.
    crop_points: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    submission: Mapped["Submission"] = relationship(back_populates="scan_images")  # noqa: F821
