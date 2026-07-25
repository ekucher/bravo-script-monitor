from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OrganizationRead(OrganizationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class InstallationCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=100)
    environment: str = Field(default="production", min_length=1, max_length=50)
    metadata_json: dict[str, object] = Field(default_factory=dict)


class InstallationRead(InstallationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
