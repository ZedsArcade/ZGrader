import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, Sequence, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from zgrader.db import Base
from zgrader.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

#: Where submission codes come from. A sequence rather than COUNT(*) + 1,
#: which is what this used to be and which handed the same code out twice.
#:
#: Deleting a submission lowered the count, so the next one reused a code that
#: had already existed. That is a unique-constraint 500 if a row still holds it,
#: and worse if none does: the scans and reports directories are named after the
#: code and are NOT removed by a database delete, so a new customer's
#: submission lands in a directory belonging to someone else's. On this
#: deployment that surfaced as a PermissionError writing the first report --
#: the leftover directory was owned by an earlier APP_UID, so it could neither
#: be written to nor cleaned up.
#:
#: A sequence never goes backwards, so a code is issued once and never again,
#: whatever happens to the rows. nextval is also non-transactional: a create
#: that rolls back leaves a gap rather than recycling the number, which is the
#: right trade -- gaps are harmless, reuse is not.
#:
#: Attached to the metadata so `create_all` builds it too. Otherwise the test
#: database would lack it and every submission test would fail against a
#: schema production does not have -- the create_all/migration split that
#: AGENTS.md warns about.
SUBMISSION_CODE_SEQUENCE = "submission_code_seq"
submission_code_seq = Sequence(SUBMISSION_CODE_SEQUENCE, metadata=Base.metadata)


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
    # Findings the client dismissed as mistaken auto-detections, as
    # "{side}:{category}:{region_id}" keys (e.g. "front:surface:blob_2").
    # The assessment (category scores + company comparisons) is recomputed
    # ignoring these -- see zgrader.analysis.recompute. NULL == none
    # dismissed.
    dismissed_regions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
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

    @property
    def scan_sides(self) -> list[str]:
        """Which sides have a registered scan -- lets callers (the upload
        endpoint, the frontend) distinguish "nothing uploaded", "front only
        (partial check)", and "both" without those being separate
        SubmissionStatus values."""
        return sorted({s.side.value for s in self.scan_images})

    @property
    def client_adjusted(self) -> bool:
        """True when the client has dismissed at least one auto-detected
        finding, so the assessment (and report) must be marked adjusted."""
        return bool(self.dismissed_regions)

    @property
    def confirmed_sides(self) -> list[str]:
        """Which sides have a *confirmed* crop (ScanImage.crop_points set)
        and are therefore eligible for analysis. A self-serve upload is
        registered (appears in scan_sides) before it's confirmed (appears
        here) -- the manual crop-adjust UI is what sets crop_points.
        Operator flatbed-drop scans get auto-confirmed at registration, so
        for that path this is always identical to scan_sides."""
        return sorted({s.side.value for s in self.scan_images if s.crop_points is not None})
