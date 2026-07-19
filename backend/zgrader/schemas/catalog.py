from pydantic import BaseModel, ConfigDict


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game: str
    verified: bool


class BrandingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_name: str
    business_contact: str | None
