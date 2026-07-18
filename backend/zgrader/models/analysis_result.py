import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AnalysisCategory(str, enum.Enum):
    centering = "centering"
    corners = "corners"
    edges = "edges"
    surface = "surface"


class AnalysisSide(str, enum.Enum):
    front = "front"
    back = "back"
    combined = "combined"


class AnalysisResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analysis_results"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False
    )
    category: Mapped[AnalysisCategory] = mapped_column(
        Enum(AnalysisCategory, name="analysis_category"), nullable=False
    )
    side: Mapped[AnalysisSide] = mapped_column(
        Enum(AnalysisSide, name="analysis_side"), nullable=False
    )
    # 0-10 scale, matching the familiar BGS/PSA-style subgrade range.
    raw_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    # Category-specific structured measurements, e.g. centering's
    # {"lr_ratio": [58, 42], "tb_ratio": [55, 45], "lr_offset_mm": 1.1, ...}
    measurements: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    annotated_image_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Free-form flags surfaced in the report, e.g.
    # {"lower_confidence": true, "reason": "flatbed scan, no raking light"}
    flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    submission: Mapped["Submission"] = relationship(back_populates="analysis_results")  # noqa: F821
