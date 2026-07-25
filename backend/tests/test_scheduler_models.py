from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.database import Base
from app.scheduler.models import JobPriority, RetryBackoff, Schedule, ScheduleKind, ScheduleRun
from app.scheduler.schemas import ScheduleCreate


def test_scheduler_tables_registered_in_metadata() -> None:
    assert "schedules" in Base.metadata.tables
    assert "schedule_runs" in Base.metadata.tables


def test_schedule_model_has_operational_indexes() -> None:
    table = Schedule.__table__
    index_names = {index.name for index in table.indexes}

    assert "ix_schedules_due" in index_names
    assert "ix_schedules_organization_enabled" in index_names
    assert "ix_schedules_next_run_at" in index_names


def test_schedule_run_is_idempotent_per_due_time() -> None:
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in ScheduleRun.__table__.constraints
        if hasattr(constraint, "columns")
    }

    assert ("schedule_id", "scheduled_for") in unique_constraints


def test_cron_schedule_schema_defaults() -> None:
    payload = ScheduleCreate(
        organization_id=uuid4(),
        script_version_id=uuid4(),
        name="Nightly backup verification",
        kind=ScheduleKind.cron,
        cron_expression="0 2 * * *",
        timezone="Europe/Kyiv",
    )

    assert payload.enabled is True
    assert payload.priority is JobPriority.normal
    assert payload.retry_count == 0
    assert payload.retry_delay_seconds == 60
    assert payload.retry_backoff is RetryBackoff.fixed
    assert payload.timeout_seconds == 3600
    assert payload.max_parallel == 1


def test_one_time_schedule_requires_run_at() -> None:
    with pytest.raises(ValidationError, match="require run_at"):
        ScheduleCreate(
            organization_id=uuid4(),
            script_version_id=uuid4(),
            name="Run once",
            kind=ScheduleKind.once,
        )


def test_cron_schedule_rejects_run_at() -> None:
    with pytest.raises(ValidationError, match="forbid run_at"):
        ScheduleCreate(
            organization_id=uuid4(),
            script_version_id=uuid4(),
            name="Invalid cron",
            kind=ScheduleKind.cron,
            cron_expression="*/5 * * * *",
            run_at=datetime.now(UTC) + timedelta(hours=1),
        )


def test_schedule_rejects_unknown_timezone() -> None:
    with pytest.raises(ValidationError, match="Unknown IANA timezone"):
        ScheduleCreate(
            organization_id=uuid4(),
            script_version_id=uuid4(),
            name="Invalid timezone",
            kind=ScheduleKind.cron,
            cron_expression="0 * * * *",
            timezone="Europe/Not-A-City",
        )
