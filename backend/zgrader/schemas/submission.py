import datetime
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from zgrader.models import SubmissionLanguage, SubmissionStatus


class QuotaOut(BaseModel):
    """How many checks the signed-in account has left, and when they return.

    `unlimited` is sent explicitly rather than left to be inferred from a null
    limit, so the UI never has to decide what a missing number means -- an
    unlimited plan shows no counter at all rather than a zero or an infinity
    symbol.
    """

    plan: str
    unlimited: bool
    limit: int | None
    used: int
    remaining: int | None
    period_days: int
    # Absolute instant the allowance returns, so the client can count down to
    # it without the server and browser needing agreeing clocks beyond UTC.
    # Null when unlimited, or before the first submission has started a window.
    resets_at: datetime.datetime | None


class SubmissionCreate(BaseModel):
    game: str
    card_name: str
    set_name: str | None = None
    card_number: str | None = None
    foil: bool = False
    language: SubmissionLanguage = SubmissionLanguage.en


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game: str
    card_name: str
    set_name: str | None
    card_number: str | None
    foil: bool


class SubmissionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submission_code: str
    status: SubmissionStatus
    created_at: datetime.datetime


class AnalysisResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    side: str
    # Nullable, and the whole point of the column being nullable: a category
    # that could not be measured has no score, which is a different answer from
    # a bad one. This stayed a bare `float` when AnalysisResult.raw_score became
    # nullable, so the moment a real card produced an unmeasurable category --
    # a full-art centering read, or corners on a capture below the resolution
    # floor -- FastAPI refused to serialise its own response and every request
    # touching that submission returned 500, confirm-crop included. The
    # pipeline was right; the contract at the edge was the last thing still
    # insisting every category has a number.
    raw_score: float | None
    measurements: dict
    flags: dict


class ComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    company: str
    category: str
    severity: str
    contention_note: str


class SubmissionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_code: str
    status: SubmissionStatus
    created_at: datetime.datetime
    notes: str | None
    auto_publish: bool | None
    card: CardOut | None
    scan_sides: list[str] = []
    confirmed_sides: list[str] = []
    dismissed_regions: list[str] = []
    analysis_results: list[AnalysisResultOut] = []
    company_comparisons: list[ComparisonOut] = []

    @field_validator("dismissed_regions", mode="before")
    @classmethod
    def _none_to_empty(cls, value: object) -> object:
        # The column is nullable JSONB (NULL == none dismissed); coerce to []
        # so the API always returns a list.
        return value or []


class CropPointsIn(BaseModel):
    points: list[tuple[float, float]]


class CropCheckOut(BaseModel):
    """Whether a candidate crop would let the card's edges be fitted.

    Asked before the crop is confirmed, because confirming it advances the
    state machine and spends the submission. Without this the first a customer
    hears about an unusable crop is a finished report with no scores in it.

    `limitations` are codes rather than sentences, matching the analysis
    contract -- the frontend already has localised copy for
    `geometry_unverified` and reuses it here rather than inventing a second
    wording for the same condition.
    """

    boundary_found: bool
    limitations: list[str]


class RegionToggleIn(BaseModel):
    region_key: str
    dismissed: bool
