import datetime
import re
import uuid
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from zgrader.models import ContactTopic

_ALLOWED_URL_SCHEMES = {"http", "https"}


def normalize_public_url(value: str | None) -> str | None:
    """Validate an operator-supplied URL that will be rendered into an href.

    A `javascript:` or `data:` URL stored here would be persistent XSS against
    every visitor to the public site, so only real web addresses are accepted
    and anything else is rejected outright rather than silently stripped --
    a saved-but-ignored value would look like it worked.

    Blank is treated as "not set", which is how the frontend hides the link.
    """
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    parsed = urlparse(trimmed)
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES or not parsed.netloc:
        raise ValueError("Must be a full http:// or https:// web address")
    return trimmed


def normalize_phone(value: str | None) -> str | None:
    """WhatsApp is stored as digits only, in international format without the
    leading '+'. The frontend builds the wa.me link from it, so no
    operator-supplied URL scheme ever reaches an href."""
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    if not digits:
        return None
    if not 6 <= len(digits) <= 20:
        raise ValueError("Must be a phone number in international format (digits only)")
    return digits


class UserQuotaOut(BaseModel):
    """A customer's quota, for the operator's support view."""

    user_id: uuid.UUID
    email: str
    plan: str
    unlimited: bool
    limit: int | None
    used: int
    remaining: int | None
    resets_at: datetime.datetime | None


class UserQuotaUpdate(BaseModel):
    """Put credits back when something went wrong for a customer.

    Expressed as `remaining` rather than the internal used-counter: an
    operator helping someone thinks in "how many do they have left", and
    making them compute `limit - remaining` is how off-by-ones happen.
    """

    remaining: int | None = Field(default=None, ge=0, le=10_000)
    # Start a fresh window now, so the countdown restarts from full. Applied
    # before `remaining`, so the two can be combined.
    reset_period: bool = False


class PlanEntitlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: str
    # None = unlimited submissions on this plan.
    submission_limit: int | None
    period_days: int


class PlanEntitlementUpdate(BaseModel):
    # Explicitly nullable: clearing the limit is how a plan is made unlimited,
    # so None here means "unlimited", not "leave unchanged". The endpoint uses
    # exclude_unset to tell the two apart.
    submission_limit: int | None = Field(default=None, ge=0, le=10_000)
    period_days: int | None = Field(default=None, ge=1, le=365)


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    auto_publish_default: bool
    business_name: str
    care_business_name: str
    business_logo_path: str | None
    business_contact: str | None
    disclaimer_text: str
    contact_email: str | None
    contact_location: str | None
    contact_response_days: int | None
    contact_in_person: bool
    social_instagram: str | None
    social_facebook: str | None
    social_x: str | None
    social_whatsapp: str | None
    centering_adjust_limit_mm: float


class SettingsUpdate(BaseModel):
    auto_publish_default: bool | None = None
    business_name: str | None = None
    care_business_name: str | None = None
    business_logo_path: str | None = None
    business_contact: str | None = None
    disclaimer_text: str | None = None
    contact_email: EmailStr | None = None
    contact_location: str | None = None
    contact_response_days: int | None = Field(default=None, ge=1, le=90)
    contact_in_person: bool | None = None
    social_instagram: str | None = None
    social_facebook: str | None = None
    social_x: str | None = None
    social_whatsapp: str | None = None
    # How far a client may move a centering line, in mm. 0 disables the
    # feature; the cap is enforced server-side in the adjust endpoint, so this
    # is the only place that decides it. Bounded at 10 because a card's
    # printed border is a few millimetres wide -- past that the "limit" would
    # let a line be placed anywhere and stop meaning anything.
    centering_adjust_limit_mm: float | None = Field(default=None, ge=0, le=10)

    @field_validator("social_instagram", "social_facebook", "social_x")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        return normalize_public_url(value)

    @field_validator("social_whatsapp")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value)

    @field_validator("contact_email", mode="before")
    @classmethod
    def _blank_email_is_unset(cls, value: object) -> object:
        # The admin form submits "" for a cleared field; EmailStr would reject
        # that, leaving the operator unable to remove an address once set.
        if isinstance(value, str) and not value.strip():
            return None
        return value


class GradingCompanyOut(BaseModel):
    """A company's presence in the multi-company comparison.

    `active` is stored per tolerance rule rather than per company (one rule
    per category), so this is the aggregate: a company counts as active when
    all of its rules are.
    """

    company: str
    active: bool
    rule_count: int


class GradingCompanyUpdate(BaseModel):
    active: bool


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


class ContactMessageOut(BaseModel):
    """A contact-form enquiry, for the operator's inbox.

    `notified` is here rather than left internal because it is the difference
    between "you have already seen this by email" and "this row is the only
    copy" -- which is the normal case while SMTP is unconfigured.

    client_ip is deliberately not exposed. It exists for abuse triage in the
    database and putting it on screen would make an ordinary enquiry look like
    a security event.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime.datetime
    name: str
    email: str
    topic: ContactTopic
    subject: str
    message: str
    language: str
    submission_code: str | None
    notified: bool
    handled: bool


class ContactMessageUpdate(BaseModel):
    """Only `handled` is editable -- the enquiry itself is what someone wrote
    and must not be rewritten from the admin panel."""

    handled: bool


class TestEmailRequest(BaseModel):
    """Where to send the diagnostic. Free-form rather than defaulting to the
    operator's own account, because the useful test is often "does mail reach
    an external provider" -- Gmail and Outlook are the two that reject
    unauthenticated senders, and the operator's own domain would not show
    that."""

    to: EmailStr


class TestEmailResponse(BaseModel):
    """`sent` is the SMTP result, not an acknowledgement.

    Everything else in the app treats a mail failure as a non-event, so this
    is the only place the truth surfaces. False means the relay refused it or
    was unreachable; True means the relay accepted it, which is still not the
    same as it reaching an inbox.
    """

    sent: bool
    detail: str
