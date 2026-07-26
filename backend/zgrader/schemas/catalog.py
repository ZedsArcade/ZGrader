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
    business_contact: str | None
    contact_email: str | None
    contact_location: str | None
    contact_response_days: int | None
    contact_in_person: bool
    social_instagram: str | None
    social_facebook: str | None
    social_x: str | None
    social_whatsapp: str | None
    # The companies currently taking part in the comparison. Published so the
    # public copy can name exactly those, rather than hardcoding a list that
    # would start lying the moment an operator disables one.
    grading_companies: list[str]
