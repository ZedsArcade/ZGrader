import datetime
import uuid

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    # Widths mirror models/card.py exactly. Without them an overlong value
    # reaches Postgres and raises StringDataRightTruncation, which surfaces as
    # a 500 where a 422 belongs -- and these strings also reach the report PDF,
    # the link-preview image and the public share page.
    game: str = Field(min_length=1, max_length=100)
    # Optional: the photo-first page creates the draft from the photo, and the
    # name is a label the customer may add later with PATCH .../card.
    card_name: str | None = Field(default=None, max_length=200)
    set_name: str | None = Field(default=None, max_length=200)
    card_number: str | None = Field(default=None, max_length=50)
    foil: bool = False
    language: SubmissionLanguage = SubmissionLanguage.en
    # The card is coming by post. Needs a name -- the operator matches the
    # physical card by it -- and is exempt from the open-draft cap.
    mail_in: bool = False

    @field_validator("card_name", mode="before")
    @classmethod
    def _blank_name_is_none(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def _mail_in_needs_a_name(self) -> "SubmissionCreate":
        if self.mail_in and not self.card_name:
            raise ValueError("A card sent by post needs a name, so it can be matched when it arrives.")
        return self


class CardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game: str
    card_name: str | None
    set_name: str | None
    card_number: str | None
    foil: bool


class SubmissionSummary(BaseModel):
    """One row of the customer's list: enough to tell ten cards apart."""

    submission_code: str
    status: SubmissionStatus
    created_at: datetime.datetime
    card_name: str | None = None
    game: str | None = None
    mail_in: bool = False
    charged: bool = False
    # The four combined category scores once analysed; None = unmeasurable,
    # never zero. Empty before any analysis.
    scores: dict[str, float | None] = {}


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
    # Whether a check has been spent on this submission. Read from the
    # model's `charged` property (charged_at is not None).
    charged: bool = False
    mail_in: bool = False
    card: CardOut | None
    scan_sides: list[str] = []
    confirmed_sides: list[str] = []
    dismissed_regions: list[str] = []
    # Per side, the border widths the client moved the centering lines to, as
    # {"front": {"left_px": .., "right_px": .., "top_px": .., "bottom_px": ..}}.
    # Exposed because the adjuster has to open showing the lines where the
    # client last put them rather than back at the detected positions -- the
    # AnalysisResult only ever holds what was measured, by design, so without
    # this the UI has no way to read back an applied adjustment.
    centering_adjustments: dict[str, dict[str, float]] = {}
    analysis_results: list[AnalysisResultOut] = []
    company_comparisons: list[ComparisonOut] = []

    @field_validator("dismissed_regions", mode="before")
    @classmethod
    def _none_to_empty(cls, value: object) -> object:
        # The column is nullable JSONB (NULL == none dismissed); coerce to []
        # so the API always returns a list.
        return value or []

    @field_validator("centering_adjustments", mode="before")
    @classmethod
    def _none_to_empty_map(cls, value: object) -> object:
        # Same, for the nullable JSONB map (NULL == nothing adjusted).
        return value or {}


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

    `crop_disagreement_sides` names which side(s) of the crop disagreed with
    the card edge found in the image, when that is why the boundary was not
    found -- filled from the rectified geometry block's own
    `crop_disagreement_sides`. Without it the crop-adjust UI could say only
    that *something* about the crop was wrong, not what to drag.
    """

    boundary_found: bool
    limitations: list[str]
    crop_disagreement_sides: list[str] = []


class RegionToggleIn(BaseModel):
    region_key: str
    dismissed: bool


class CenteringAdjustIn(BaseModel):
    """Border widths a client has moved, in pixels of the rectified raster.

    Pixels rather than millimetres because that is the space the stored
    measurement and the on-screen overlay both live in -- converting at the
    edges would put a rounding step between what the customer dragged and what
    gets scored.

    All four are required. A ratio needs both of its sides, and accepting a
    partial set would mean guessing the other one, which is how a missing
    measurement once became a confident 100/0 split.
    """

    side: Literal["front", "back"]
    left_px: float = Field(ge=0)
    right_px: float = Field(ge=0)
    top_px: float = Field(ge=0)
    bottom_px: float = Field(ge=0)


class CardUpdate(BaseModel):
    """Edits to a submission's card. Omitted fields are left alone; `null`
    clears a label. Widths mirror models/card.py, as SubmissionCreate's do."""

    model_config = ConfigDict(extra="forbid")

    card_name: str | None = Field(default=None, max_length=200)
    set_name: str | None = Field(default=None, max_length=200)
    card_number: str | None = Field(default=None, max_length=50)
    foil: bool | None = None
