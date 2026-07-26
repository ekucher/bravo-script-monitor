from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.scheduler.engine import calculate_next_run_at, initialize_next_run_at
from app.scheduler.models import Schedule, ScheduleKind


def test_calculate_next_run_at_uses_schedule_timezone() -> None:
    after = datetime(2026, 7, 26, 20, 30, tzinfo=UTC)

    next_run = calculate_next_run_at("0 2 * * *", "Europe/Kyiv", after)

    assert next_run == datetime(2026, 7, 26, 23, 0, tzinfo=UTC)


def test_calculate_next_run_at_rejects_naive_reference() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_next_run_at("0 2 * * *", "UTC", datetime(2026, 7, 26, 20, 30))


def test_initialize_once_schedule_uses_run_at() -> None:
    run_at = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
    schedule = Schedule(
        organization_id=uuid4(),
        script_version_id=uuid4(),
        name="One time",
        enabled=True,
        kind=ScheduleKind.once,
        cron_expression=None,
        timezone="UTC",
        run_at=run_at,
    )

    assert initialize_next_run_at(schedule) == run_at


def test_initialize_disabled_schedule_returns_none() -> None:
    schedule = Schedule(
        organization_id=uuid4(),
        script_version_id=uuid4(),
        name="Disabled",
        enabled=False,
        kind=ScheduleKind.cron,
        cron_expression="*/5 * * * *",
        timezone="UTC",
        run_at=None,
    )

    assert initialize_next_run_at(schedule) is None


def test_initialize_cron_schedule_calculates_first_run() -> None:
    schedule = Schedule(
        organization_id=uuid4(),
        script_version_id=uuid4(),
        name="Hourly",
        enabled=True,
        kind=ScheduleKind.cron,
        cron_expression="0 * * * *",
        timezone="UTC",
        run_at=None,
    )

    next_run = initialize_next_run_at(
        schedule,
        datetime(2026, 7, 26, 20, 30, tzinfo=UTC),
    )

    assert next_run == datetime(2026, 7, 26, 21, 0, tzinfo=UTC)
