import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SubmissionStatus(str, enum.Enum):
    created = "created"
    awaiting_scans = "awaiting_scans"
    processing = "processing"
    draft_ready = "draft_ready"
    approved = "approved"
    published = "published"
    error = "error"


class SubmissionLanguage(str, enum.Enum):
    """Language the client had active when creating the submission --
    drives which language the PDF report and notification emails render
    in. Not a per-account preference; captured once at creation time."""

    en = "en"
    es = "es"


class Submission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One Submission == one physical card's grading job.

    A client ordering multiple cards gets multiple Submissions created
    together (sharing `batch_id`), rather than nesting multiple cards under
    one folder -- this keeps the watcher's folder-name-to-submission match
    a simple 1:1 lookup.
    """

    __tablename__ = "submissions"

    submission_code: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status"),
        default=SubmissionStatus.created,
        nullable=False,
    )
    # Null = inherit the global Settings.auto_publish_default; True/False
    # explicitly overrides it for this submission only.
    auto_publish: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[SubmissionLanguage] = mapped_column(
        Enum(SubmissionLanguage, name="submission_language"),
        default=SubmissionLanguage.en,
        server_default=SubmissionLanguage.en.value,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="submissions", foreign_keys=[user_id])  # noqa: F821
    card: Mapped["Card"] = relationship(  # noqa: F821
        back_populates="submission", uselist=False, cascade="all, delete-orphan"
    )
    scan_images: Mapped[list["ScanImage"]] = relationship(  # noqa: F821
        back_populates="submission", cascade="all, delete-orphan"
    )
    analysis_results: Mapped[list["AnalysisResult"]] = relationship(  # noqa: F821
        back_populates="submission", cascade="all, delete-orphan"
    )
    company_comparisons: Mapped[list["GradingCompanyComparison"]] = relationship(  # noqa: F821
        back_populates="submission", cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(  # noqa: F821
        back_populates="submission", cascade="all, delete-orphan"
    )
