from __future__ import annotations

import math
from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import JobStatus
from app.scheduler.models import JobPriority, MisfirePolicy, RetryBackoff, ScheduleKind


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown IANA timezone") from exc
    return value


def validate_cron_expression(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized.split(" ")) != 5:
        raise ValueError("Cron expression must contain exactly five fields")
    return normalized


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

    @field_validator("timezone")
    @classmethod
    def validate_timezone_field(cls, value: str) -> str:
        return validate_timezone(value)

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_field(cls, value: str | None) -> str | None:
        return validate_cron_expression(value)

    @model_validator(mode="after")
    def validate_schedule_configuration(self) -> ScheduleBase:
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
    script_version_id: UUID | None = None
    agent_id: UUID | None = None
    enabled: bool | None = None
    kind: ScheduleKind | None = None
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

    @field_validator("timezone")
    @classmethod
    def validate_optional_timezone(cls, value: str | None) -> str | None:
        return validate_timezone(value) if value is not None else None

    @field_validator("cron_expression")
    @classmethod
    def validate_optional_cron(cls, value: str | None) -> str | None:
        return validate_cron_expression(value)


class ScheduleRead(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SchedulePage(BaseModel):
    items: list[ScheduleRead]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(
        cls,
        items: list[ScheduleRead],
        total: int,
        page: int,
        page_size: int,
    ) -> SchedulePage:
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )


class ManualJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    script_version_id: UUID
    status: JobStatus
    parameters: dict
    scheduled_for: datetime | None
    created_at: datetime
    updated_at: datetime


ScheduleSortField = Literal["name", "created_at", "updated_at", "next_run_at"]
SortDirection = Literal["asc", "desc"]
