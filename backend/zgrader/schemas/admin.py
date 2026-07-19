import datetime
import uuid

from pydantic import BaseModel, ConfigDict


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auto_publish_default: bool
    business_name: str
    business_logo_path: str | None
    business_contact: str | None
    disclaimer_text: str


class SettingsUpdate(BaseModel):
    auto_publish_default: bool | None = None
    business_name: str | None = None
    business_logo_path: str | None = None
    business_contact: str | None = None
    disclaimer_text: str | None = None


class StatsOut(BaseModel):
    total_submissions: int
    by_status: dict[str, int]
    published_reports: int


class AutoPublishUpdate(BaseModel):
    auto_publish: bool | None  # null clears the per-submission override


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    action: str
    detail: dict
    submission_code: str | None
    user_email: str | None
