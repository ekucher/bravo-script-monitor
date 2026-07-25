from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import AgentStatus, JobStatus


class AgentRegistrationRequest(BaseModel):
    installation_id: UUID
    hostname: str = Field(min_length=1, max_length=255)
    agent_name: str = Field(default="default", min_length=1, max_length=100)
    version: str | None = Field(default=None, max_length=50)
    operating_system: str | None = Field(default=None, max_length=255)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    inventory: dict[str, Any] = Field(default_factory=dict)


class AgentRegistrationResponse(BaseModel):
    agent_id: UUID
    token: str
    status: AgentStatus
    registered_at: datetime


class AgentHeartbeatRequest(BaseModel):
    version: str | None = Field(default=None, max_length=50)
    capabilities: dict[str, Any] | None = None


class AgentInventoryRequest(BaseModel):
    operating_system: str | None = Field(default=None, max_length=255)
    inventory: dict[str, Any] = Field(default_factory=dict)


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    server_id: UUID
    name: str
    version: str | None
    status: AgentStatus
    last_seen_at: datetime | None
    capabilities: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AgentJobRead(BaseModel):
    id: UUID
    status: JobStatus
    script_version_id: UUID
    parameters: dict[str, Any]
    scheduled_for: datetime | None
    script: str
    script_sha256: str


class AgentJobResultRequest(BaseModel):
    status: JobStatus
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
