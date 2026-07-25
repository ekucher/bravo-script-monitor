from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.scheduler.models import JobPriority, MisfirePolicy, RetryBackoff, ScheduleKind


class ScheduleBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    script_version_id: UUID
    agent_id: UUID | None = None
    enabled: bool = True
    kind: ScheduleKind
    cron_expression: str | None = Field(default=None, min_length=5, max_length=100)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    run_at: datetime | None = None
    parameters: dict = Field(default_factory=dict)
    target_filter: dict = Field(default_factory=dict)
    priority: JobPriority = JobPriority.normal
    retry_count: int = Field(default=0, ge=0, le=100)
    retry_delay_seconds: int = Field(default=60, ge=0, le=86400)
    retry_backoff: RetryBackoff = RetryBackoff.fixed
    timeout_seconds: int = Field(default=3600, ge=1, le=604800)
    max_parallel: int = Field(default=1, ge=1, le=1000)
    misfire_policy: MisfirePolicy = MisfirePolicy.skip

    @model_validator(mode="after")
    def validate_schedule_configuration(self) -> "ScheduleBase":
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc

        if self.kind is ScheduleKind.cron:
            if self.cron_expression is None or self.run_at is not None:
                raise ValueError("Cron schedules require cron_expression and forbid run_at")
        elif self.run_at is None or self.cron_expression is not None:
            raise ValueError("One-time schedules require run_at and forbid cron_expression")
        return self


class ScheduleCreate(ScheduleBase):
    organization_id: UUID


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    enabled: bool | None = None
    cron_expression: str | None = Field(default=None, min_length=5, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=100)
    run_at: datetime | None = None
    parameters: dict | None = None
    target_filter: dict | None = None
    priority: JobPriority | None = None
    retry_count: int | None = Field(default=None, ge=0, le=100)
    retry_delay_seconds: int | None = Field(default=None, ge=0, le=86400)
    retry_backoff: RetryBackoff | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=604800)
    max_parallel: int | None = Field(default=None, ge=1, le=1000)
    misfire_policy: MisfirePolicy | None = None


class ScheduleRead(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
