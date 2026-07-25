import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$")
ScriptLanguage = Literal["powershell", "bash", "python"]


def validate_semver(value: str) -> str:
    if not SEMVER_PATTERN.fullmatch(value):
        raise ValueError("Version must follow Semantic Versioning, for example 1.2.3")
    return value


class ScriptCreate(BaseModel):
    organization_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class ScriptUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ScriptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class ScriptVersionCreate(BaseModel):
    version: str
    language: ScriptLanguage
    content: str = Field(min_length=1, max_length=2_000_000)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)

    _validate_version = field_validator("version")(validate_semver)


class ScriptVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    script_id: UUID
    version: str
    content: str
    sha256: str
    parameter_schema: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @property
    def language(self) -> str | None:
        repository = self.parameter_schema.get("_repository", {})
        return repository.get("language")

    @property
    def published(self) -> bool:
        repository = self.parameter_schema.get("_repository", {})
        return bool(repository.get("published", False))


class ScriptVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    script_id: UUID
    version: str
    sha256: str
    parameter_schema: dict[str, Any]
    created_at: datetime
    updated_at: datetime
