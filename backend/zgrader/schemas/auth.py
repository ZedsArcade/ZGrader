import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from zgrader.models import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    is_verified: bool
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
