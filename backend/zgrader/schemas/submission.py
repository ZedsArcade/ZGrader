import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from zgrader.models import SubmissionStatus


class SubmissionCreate(BaseModel):
    game: str
    card_name: str
    set_name: str | None = None
    card_number: str | None = None
    foil: bool = False


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
    raw_score: float
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
    card: CardOut | None
    analysis_results: list[AnalysisResultOut] = []
    company_comparisons: list[ComparisonOut] = []
