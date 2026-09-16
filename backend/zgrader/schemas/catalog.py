from pydantic import BaseModel, ConfigDict


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game: str
    verified: bool


class BrandingOut(BaseModel):
    """Public, unauthenticated branding + contact details.

    Everything here is meant to be read by anonymous visitors -- it is what the
    nav, footer and contact page render. Operator-only settings
    (auto_publish_default, disclaimer_text) stay on the authed SettingsOut.
    """

    model_config = ConfigDict(from_attributes=True)

    business_name: str
    # The care/restoration brand, shown by the header's section toggle and on
    # the /care pages. Public because the nav renders it on every page.
    care_business_name: str
    business_contact: str | None
    contact_email: str | None
    contact_location: str | None
    contact_response_days: int | None
    contact_in_person: bool
    social_instagram: str | None
    social_facebook: str | None
    social_x: str | None
    social_whatsapp: str | None
    # Public because the results page needs it to bound the centering drag
    # handles. Not sensitive -- it is a limit, not a credential.
    centering_adjust_limit_mm: float
    # Where a hand-placed centering line may sit (0 to max mm from the card's
    # edge) and where an unfound side's line starts. Constants in
    # analysis/scoring.py rather than settings, published so the page bounds
    # its handles with the numbers the endpoint enforces.
    centering_placement_max_mm: float
    centering_placement_default_mm: float
    # The companies currently taking part in the comparison. Published so the
    # public copy can name exactly those, rather than hardcoding a list that
    # would start lying the moment an operator disables one.
    grading_companies: list[str]


class PlanPriceOut(BaseModel):
    """One software tier as the public pricing page shows it.

    Allowance and price come from the same row on purpose. They used to live in
    two places -- the cap in `plan_entitlements`, the price in the site copy --
    and the copy said "the first check is free" while the seed granted three a
    week. Publishing them together is what stops the quote and the enforcement
    describing different products.
    """

    model_config = ConfigDict(from_attributes=True)

    plan: str
    # None = unlimited checks.
    submission_limit: int | None
    period_days: int
    # None = not sold; granted rather than bought.
    price_pence: int | None
    # "month", "year" or "once". None when nothing is charged.
    billing_period: str | None


class PhysicalPriceTierOut(BaseModel):
    """One band of the in-hand volume table."""

    model_config = ConfigDict(from_attributes=True)

    min_qty: int
    # None = the open-ended top band, "and up".
    max_qty: int | None
    price_pence: int


class PricingOut(BaseModel):
    """Everything the public pricing page needs, in one request.

    Nothing here is a credential and nothing is per-user: these are the prices
    on the shopfront, so the endpoint is unauthenticated like the rest of
    /catalog. Amounts are whole pence, GBP.
    """

    plans: list[PlanPriceOut]
    physical_tiers: list[PhysicalPriceTierOut]
    # Loose figures, each None when the offer is switched off -- which is a
    # different thing from it being free.
    collection_triage_guide_pence: int | None
    founder_price_pence: int | None
    founder_seats: int | None
    subscriber_discount_pct: int | None
    # Whether Subscribe can be offered. False keeps "Get in touch" on the page
    # rather than a button into a checkout this deployment cannot run.
    billing_enabled: bool
    # Seats left at the founder price; None when the offer is off. One
    # aggregate, nothing per user -- safe on an unauthenticated route.
    founder_seats_remaining: int | None
    # The Terms version the checkout confirm must echo back, so a customer
    # always accepts the version the server currently enforces.
    terms_version: str
