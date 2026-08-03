import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from zgrader.models import UserRole

# bcrypt silently ignores anything past 72 bytes, so accepting more would
# mean a passphrase whose tail does nothing -- reject it instead of quietly
# truncating the user's secret.
_PASSWORD = Field(min_length=8, max_length=72)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = _PASSWORD
    # Required and must be true: the account can't be created without an
    # explicit agreement to the terms, which is what makes them enforceable.
    accept_terms: bool
    marketing_consent: bool = False

    @field_validator("accept_terms")
    @classmethod
    def _must_accept(cls, value: bool) -> bool:
        if not value:
            raise ValueError("The terms and privacy policy must be accepted to register.")
        return value


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=64)
    password: str = _PASSWORD


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = _PASSWORD


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_verified: bool
    role: UserRole
    display_name: str | None = None
    marketing_consent: bool = False
    terms_accepted_at: datetime.datetime | None = None


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=200)
    marketing_consent: bool | None = None


class GoogleStatusOut(BaseModel):
    """Whether this deployment has Google sign-in configured, so the frontend
    can decide whether to render the button at all."""

    enabled: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
