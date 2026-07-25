from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_permission
from app.database import get_db_session
from app.scheduler.models import Schedule, ScheduleKind, ScheduleRun
from app.scheduler.schemas import (
    ManualJobRead,
    ScheduleCreate,
    SchedulePage,
    ScheduleRead,
    ScheduleSortField,
    ScheduleUpdate,
    SortDirection,
)
from app.scheduler.service import (
    count_schedules,
    create_schedule,
    get_schedule_or_404,
    run_schedule_now,
    set_schedule_enabled,
    update_schedule,
)

DbSession = Annotated[Session, Depends(get_db_session)]
router = APIRouter(prefix="/schedules", tags=["schedules"])


def _apply_filters(
    statement: Select[tuple[Schedule]],
    organization_id: UUID | None,
    enabled: bool | None,
    kind: ScheduleKind | None,
    agent_id: UUID | None,
    script_version_id: UUID | None,
    search: str | None,
    created_after: datetime | None,
    created_before: datetime | None,
) -> Select[tuple[Schedule]]:
    if organization_id is not None:
        statement = statement.where(Schedule.organization_id == organization_id)
    if enabled is not None:
        statement = statement.where(Schedule.enabled.is_(enabled))
    if kind is not None:
        statement = statement.where(Schedule.kind == kind)
    if agent_id is not None:
        statement = statement.where(Schedule.agent_id == agent_id)
    if script_version_id is not None:
        statement = statement.where(Schedule.script_version_id == script_version_id)
    if search is not None:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            func.lower(Schedule.name).like(func.lower(pattern))
            | func.lower(func.coalesce(Schedule.description, "")).like(func.lower(pattern))
        )
    if created_after is not None:
        statement = statement.where(Schedule.created_at >= created_after)
    if created_before is not None:
        statement = statement.where(Schedule.created_at <= created_before)
    return statement


@router.get(
    "",
    response_model=SchedulePage,
    dependencies=[Depends(require_permission("schedules.read"))],
)
def list_schedules(
    session: DbSession,
    organization_id: UUID | None = None,
    enabled: bool | None = None,
    kind: ScheduleKind | None = None,
    agent_id: UUID | None = None,
    script_version_id: UUID | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    sort_by: ScheduleSortField = "created_at",
    sort_direction: SortDirection = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 25,
) -> SchedulePage:
    statement = _apply_filters(
        select(Schedule),
        organization_id,
        enabled,
        kind,
        agent_id,
        script_version_id,
        search,
        created_after,
        created_before,
    )
    total = count_schedules(session, statement)
    sort_column = getattr(Schedule, sort_by)
    ordering = sort_column.asc() if sort_direction == "asc" else sort_column.desc()
    statement = statement.order_by(ordering, Schedule.id).offset((page - 1) * page_size).limit(page_size)
    items = [ScheduleRead.model_validate(item) for item in session.scalars(statement)]
    return SchedulePage.build(items, total, page, page_size)


@router.post(
    "",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("schedules.write"))],
)
def create_schedule_endpoint(
    payload: ScheduleCreate,
    session: DbSession,
    current_user: CurrentUser,
) -> Schedule:
    return create_schedule(session, payload, current_user.id)


@router.get(
    "/{schedule_id}",
    response_model=ScheduleRead,
    dependencies=[Depends(require_permission("schedules.read"))],
)
def get_schedule(schedule_id: UUID, session: DbSession) -> Schedule:
    return get_schedule_or_404(session, schedule_id)


@router.patch(
    "/{schedule_id}",
    response_model=ScheduleRead,
    dependencies=[Depends(require_permission("schedules.write"))],
)
def update_schedule_endpoint(
    schedule_id: UUID,
    payload: ScheduleUpdate,
    session: DbSession,
) -> Schedule:
    return update_schedule(session, get_schedule_or_404(session, schedule_id), payload)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_permission("schedules.write"))],
)
def delete_schedule(schedule_id: UUID, session: DbSession) -> Response:
    schedule = get_schedule_or_404(session, schedule_id)
    has_runs = session.scalar(
        select(ScheduleRun.id).where(ScheduleRun.schedule_id == schedule.id).limit(1)
    )
    if has_runs is not None:
        raise HTTPException(
            status_code=409,
            detail="Schedules with execution history cannot be deleted; disable the schedule instead",
        )
    session.delete(schedule)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{schedule_id}/enable",
    response_model=ScheduleRead,
    dependencies=[Depends(require_permission("schedules.write"))],
)
def enable_schedule(schedule_id: UUID, session: DbSession) -> Schedule:
    return set_schedule_enabled(session, get_schedule_or_404(session, schedule_id), True)


@router.post(
    "/{schedule_id}/disable",
    response_model=ScheduleRead,
    dependencies=[Depends(require_permission("schedules.write"))],
)
def disable_schedule(schedule_id: UUID, session: DbSession) -> Schedule:
    return set_schedule_enabled(session, get_schedule_or_404(session, schedule_id), False)


@router.post(
    "/{schedule_id}/run",
    response_model=ManualJobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("schedules.run"))],
)
def run_schedule(schedule_id: UUID, session: DbSession) -> ManualJobRead:
    job = run_schedule_now(session, get_schedule_or_404(session, schedule_id))
    return ManualJobRead.model_validate(job)
