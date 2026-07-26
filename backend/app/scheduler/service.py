from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Agent, Job, JobStatus, Organization, ScriptVersion
from app.scheduler.models import Schedule, ScheduleKind
from app.scheduler.schemas import ScheduleCreate, ScheduleUpdate


def get_schedule_or_404(session: Session, schedule_id: UUID) -> Schedule:
    schedule = session.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


def validate_schedule_references(
    session: Session,
    organization_id: UUID,
    script_version_id: UUID,
    agent_id: UUID | None,
) -> None:
    if session.get(Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    script_version = session.get(ScriptVersion, script_version_id)
    if script_version is None:
        raise HTTPException(status_code=404, detail="Script version not found")
    if script_version.script.organization_id != organization_id:
        raise HTTPException(
            status_code=409,
            detail="Script version does not belong to the selected organization",
        )

    if agent_id is not None:
        agent = session.get(Agent, agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        if agent.server.installation.organization_id != organization_id:
            raise HTTPException(
                status_code=409,
                detail="Agent does not belong to the selected organization",
            )


def create_schedule(
    session: Session,
    payload: ScheduleCreate,
    created_by_user_id: UUID | None,
) -> Schedule:
    validate_schedule_references(
        session,
        payload.organization_id,
        payload.script_version_id,
        payload.agent_id,
    )
    values = payload.model_dump()
    schedule = Schedule(**values, created_by_user_id=created_by_user_id)
    if schedule.kind is ScheduleKind.once:
        schedule.next_run_at = schedule.run_at
    session.add(schedule)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Schedule name already exists in this organization",
        ) from exc
    session.refresh(schedule)
    return schedule


def update_schedule(session: Session, schedule: Schedule, payload: ScheduleUpdate) -> Schedule:
    values = payload.model_dump(exclude_unset=True)
    candidate_script_version_id = values.get("script_version_id", schedule.script_version_id)
    candidate_agent_id = values.get("agent_id", schedule.agent_id)
    validate_schedule_references(
        session,
        schedule.organization_id,
        candidate_script_version_id,
        candidate_agent_id,
    )

    candidate = {
        "kind": values.get("kind", schedule.kind),
        "cron_expression": values.get("cron_expression", schedule.cron_expression),
        "run_at": values.get("run_at", schedule.run_at),
    }
    if candidate["kind"] is ScheduleKind.cron:
        if candidate["cron_expression"] is None or candidate["run_at"] is not None:
            raise HTTPException(
                status_code=422,
                detail="Cron schedules require cron_expression and forbid run_at",
            )
    elif candidate["run_at"] is None or candidate["cron_expression"] is not None:
        raise HTTPException(
            status_code=422,
            detail="One-time schedules require run_at and forbid cron_expression",
        )

    for field, value in values.items():
        setattr(schedule, field, value)
    if schedule.kind is ScheduleKind.once:
        schedule.next_run_at = schedule.run_at if schedule.enabled else None

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Schedule name already exists in this organization",
        ) from exc
    session.refresh(schedule)
    return schedule


def set_schedule_enabled(session: Session, schedule: Schedule, enabled: bool) -> Schedule:
    schedule.enabled = enabled
    if schedule.kind is ScheduleKind.once:
        schedule.next_run_at = schedule.run_at if enabled else None
    session.commit()
    session.refresh(schedule)
    return schedule


def run_schedule_now(session: Session, schedule: Schedule) -> Job:
    if schedule.agent_id is None:
        raise HTTPException(
            status_code=409,
            detail="Schedule must have an assigned agent before manual execution",
        )
    job = Job(
        agent_id=schedule.agent_id,
        script_version_id=schedule.script_version_id,
        status=JobStatus.pending,
        parameters=dict(schedule.parameters),
        scheduled_for=datetime.now(UTC),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def count_schedules(session: Session, statement) -> int:
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    return int(session.scalar(count_statement) or 0)
