from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import TimestampMixin


class ScheduleKind(str, enum.Enum):
    cron = "cron"
    once = "once"


class RetryBackoff(str, enum.Enum):
    fixed = "fixed"
    exponential = "exponential"


class MisfirePolicy(str, enum.Enum):
    skip = "skip"
    fire_once = "fire_once"


class JobPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_schedules_organization_name"),
        CheckConstraint("retry_count >= 0", name="ck_schedules_retry_count_non_negative"),
        CheckConstraint("retry_delay_seconds >= 0", name="ck_schedules_retry_delay_non_negative"),
        CheckConstraint("timeout_seconds > 0", name="ck_schedules_timeout_positive"),
        CheckConstraint("max_parallel > 0", name="ck_schedules_max_parallel_positive"),
        CheckConstraint(
            "(kind = 'cron' AND cron_expression IS NOT NULL AND run_at IS NULL) OR "
            "(kind = 'once' AND cron_expression IS NULL AND run_at IS NOT NULL)",
            name="ck_schedules_kind_configuration",
        ),
        Index("ix_schedules_due", "enabled", "next_run_at"),
        Index("ix_schedules_organization_enabled", "organization_id", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    script_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("script_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    kind: Mapped[ScheduleKind] = mapped_column(
        Enum(ScheduleKind, name="schedule_kind"), nullable=False
    )
    cron_expression: Mapped[str | None] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", nullable=False)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    target_filter: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    priority: Mapped[JobPriority] = mapped_column(
        Enum(JobPriority, name="job_priority"), default=JobPriority.normal, nullable=False
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    retry_backoff: Mapped[RetryBackoff] = mapped_column(
        Enum(RetryBackoff, name="retry_backoff"), default=RetryBackoff.fixed, nullable=False
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=3600, nullable=False)
    max_parallel: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    misfire_policy: Mapped[MisfirePolicy] = mapped_column(
        Enum(MisfirePolicy, name="misfire_policy"), default=MisfirePolicy.skip, nullable=False
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )


class ScheduleRun(TimestampMixin, Base):
    __tablename__ = "schedule_runs"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id", "scheduled_for", name="uq_schedule_runs_schedule_scheduled_for"
        ),
        Index("ix_schedule_runs_status_created_at", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error: Mapped[str | None] = mapped_column(String(2000))
