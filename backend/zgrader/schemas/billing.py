import datetime

from pydantic import BaseModel, ConfigDict, Field


class CheckoutIn(BaseModel):
    """The browser names a plan and confirms consent. It never sends a
    figure: extra="forbid" makes a client-supplied amount a 422 rather than
    something quietly ignored."""

    model_config = ConfigDict(extra="forbid")

    plan: str = Field(min_length=1, max_length=64)
    terms_version: str = Field(min_length=1, max_length=20)
    immediate_start_consent: bool


class CheckoutOut(BaseModel):
    url: str


class PortalOut(BaseModel):
    url: str


class SubscriptionOut(BaseModel):
    plan: str
    status: str
    entitled: bool
    founder: bool
    amount_pence: int | None
    current_period_start: datetime.datetime | None
    current_period_end: datetime.datetime | None
    cancel_at: datetime.datetime | None


class ReconcileOut(BaseModel):
    checked: int
    corrected: int
