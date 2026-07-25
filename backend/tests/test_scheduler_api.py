from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api import router as api_router
from app.scheduler.models import ScheduleKind
from app.scheduler.router import router
from app.scheduler.schemas import ScheduleCreate, SchedulePage, ScheduleRead, ScheduleUpdate


def test_scheduler_router_exposes_management_endpoints() -> None:
    paths = {route.path for route in router.routes}

    assert "/schedules" in paths
    assert "/schedules/{schedule_id}" in paths
    assert "/schedules/{schedule_id}/enable" in paths
    assert "/schedules/{schedule_id}/disable" in paths
    assert "/schedules/{schedule_id}/run" in paths


def test_scheduler_router_is_registered_in_v1_api() -> None:
    paths = {route.path for route in api_router.routes}

    assert "/api/v1/schedules" in paths
    assert "/api/v1/schedules/{schedule_id}/run" in paths


def test_cron_expression_is_normalized() -> None:
    payload = ScheduleCreate(
        organization_id=uuid4(),
        script_version_id=uuid4(),
        name="Nightly archive",
        kind=ScheduleKind.cron,
        cron_expression="0   2  * *   *",
        timezone="Europe/Kyiv",
    )

    assert payload.cron_expression == "0 2 * * *"


def test_cron_expression_requires_five_fields() -> None:
    with pytest.raises(ValidationError, match="exactly five fields"):
        ScheduleCreate(
            organization_id=uuid4(),
            script_version_id=uuid4(),
            name="Invalid cron",
            kind=ScheduleKind.cron,
            cron_expression="0 2 * *",
        )


def test_schedule_update_validates_timezone() -> None:
    with pytest.raises(ValidationError, match="Unknown IANA timezone"):
        ScheduleUpdate(timezone="Europe/Invalid-City")


def test_schedule_page_calculates_page_count() -> None:
    now = datetime.now(UTC)
    item = ScheduleRead(
        id=uuid4(),
        organization_id=uuid4(),
        script_version_id=uuid4(),
        agent_id=None,
        name="Nightly archive",
        description=None,
        enabled=True,
        kind=ScheduleKind.cron,
        cron_expression="0 2 * * *",
        timezone="Europe/Kyiv",
        run_at=None,
        parameters={},
        target_filter={},
        priority="normal",
        retry_count=0,
        retry_delay_seconds=60,
        retry_backoff="fixed",
        timeout_seconds=3600,
        max_parallel=1,
        misfire_policy="skip",
        next_run_at=None,
        last_run_at=None,
        created_at=now,
        updated_at=now,
    )

    page = SchedulePage.build([item], total=51, page=2, page_size=25)

    assert page.total == 51
    assert page.page == 2
    assert page.pages == 3
