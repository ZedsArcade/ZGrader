import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class GradingCompany(str, enum.Enum):
    PSA = "PSA"
    BGS = "BGS"
    CGC = "CGC"
    TAG = "TAG"


class ToleranceSeverity(str, enum.Enum):
    none = "none"
    minor = "minor"
    major = "major"


class GradingCompanyToleranceRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Pure data backing the multi-company comparison engine.

    Tunable later against real submitted-grade outcomes without touching
    Python logic -- see zgrader/analysis/rules_engine.py.
    """

    __tablename__ = "grading_company_tolerance_rules"

    company: Mapped[GradingCompany] = mapped_column(
        Enum(GradingCompany, name="grading_company"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. {"minor_at": 60, "major_at": 65} meaning the worse side of a
    # centering ratio crossing 60/40 is "minor", 65/35 is "major" for this
    # company/category/metric combination.
    thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False)
    note_template: Mapped[str] = mapped_column(Text, nullable=False)
    note_template_es: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)


class GradingCompanyComparison(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grading_company_comparisons"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("submissions.id"), nullable=False
    )
    company: Mapped[GradingCompany] = mapped_column(
        Enum(GradingCompany, name="grading_company"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[ToleranceSeverity] = mapped_column(
        Enum(ToleranceSeverity, name="tolerance_severity"), nullable=False
    )
    # Never a numeric grade prediction -- flags + reasoning only.
    contention_note: Mapped[str] = mapped_column(Text, nullable=False)

    submission: Mapped["Submission"] = relationship(back_populates="company_comparisons")  # noqa: F821
