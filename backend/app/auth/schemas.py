from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None
    email: EmailStr
    display_name: str
    is_active: bool
    is_superuser: bool
    permissions: list[str]


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    permissions: list[str] = Field(default_factory=list)
    expires_at: datetime | None = None


class ApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key: str
    key_prefix: str
    permissions: list[str]
    expires_at: datetime | None
