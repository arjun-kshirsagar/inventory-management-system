from pydantic import BaseModel, Field

from app.models.enums import Role
from app.schemas.common import ORMModel

# Plain pattern rather than EmailStr: internal addresses like admin@store.local are fine.
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: int
    email: str
    name: str
    role: Role
    is_active: bool


class UserCreate(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=255)
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=6)
    role: Role = Role.CASHIER


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=6)
    role: Role | None = None
    is_active: bool | None = None
