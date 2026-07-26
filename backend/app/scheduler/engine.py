from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Job, JobStatus
from app.scheduler.models import MisfirePolicy, Schedule, ScheduleKind, ScheduleRun


@dataclass(frozen=True, slots=True)
class SchedulerTickResult:
    inspected: int = 0
    materialized: int = 0
    skipped: int = 0
    failed: int = 0


def calculate_next_run_at(
    cron_expression: str,
    timezone: str,
    after: datetime | None = None,
) -> datetime:
    """Return the next cron occurrence as an aware UTC datetime."""
    reference = after or datetime.now(UTC)
    if reference.tzinfo is None:
        raise ValueError("after must be timezone-aware")

    local_timezone = ZoneInfo(timezone)
    local_reference = reference.astimezone(local_timezone)
    next_local = croniter(cron_expression, local_reference).get_next(datetime)
    if next_local.tzinfo is None:
        next_local = next_local.replace(tzinfo=local_timezone)
    return next_local.astimezone(UTC)


def initialize_next_run_at(schedule: Schedule, now: datetime | None = None) -> datetime | None:
    """Calculate the first due time for an enabled schedule."""
    if not schedule.enabled:
        return None
    if schedule.kind is ScheduleKind.once:
        return schedule.run_at
    if schedule.cron_expression is None:
        raise ValueError("Cron schedule is missing cron_expression")
    return calculate_next_run_at(schedule.cron_expression, schedule.timezone, now)


def _next_after_materialization(schedule: Schedule, scheduled_for: datetime) -> datetime | None:
    if schedule.kind is ScheduleKind.once:
        schedule.enabled = False
        return None
    if schedule.cron_expression is None:
        raise ValueError("Cron schedule is missing cron_expression")
    return calculate_next_run_at(schedule.cron_expression, schedule.timezone, scheduled_for)


def _materialize_schedule(session: Session, schedule: Schedule, now: datetime) -> bool:
    scheduled_for = schedule.next_run_at
    if scheduled_for is None:
        return False

    if schedule.agent_id is None:
        schedule.last_run_at = scheduled_for
        schedule.next_run_at = _next_after_materialization(schedule, scheduled_for)
        return False

    if schedule.misfire_policy is MisfirePolicy.skip and scheduled_for < now:
        schedule.last_run_at = scheduled_for
        schedule.next_run_at = _next_after_materialization(schedule, scheduled_for)
        return False

    job = Job(
        agent_id=schedule.agent_id,
        script_version_id=schedule.script_version_id,
        status=JobStatus.pending,
        parameters=dict(schedule.parameters),
        scheduled_for=scheduled_for,
    )
    run = ScheduleRun(
        schedule_id=schedule.id,
        scheduled_for=scheduled_for,
        status="pending",
        job_id=job.id,
    )
    session.add_all([job, run])
    schedule.last_run_at = scheduled_for
    schedule.next_run_at = _next_after_materialization(schedule, scheduled_for)
    return True


def process_due_schedules(
    session: Session,
    *,
    now: datetime | None = None,
    batch_size: int = 100,
) -> SchedulerTickResult:
    """Lock and materialize due schedules in one transaction.

    PostgreSQL ``FOR UPDATE SKIP LOCKED`` allows multiple scheduler workers to
    process independent rows without creating duplicate jobs.
    """
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if batch_size < 1:
        raise ValueError("batch_size must be positive")

    statement = (
        select(Schedule)
        .where(
            Schedule.enabled.is_(True),
            Schedule.next_run_at.is_not(None),
            Schedule.next_run_at <= current_time,
        )
        .order_by(Schedule.next_run_at, Schedule.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    schedules = list(session.scalars(statement))
    materialized = 0
    skipped = 0
    failed = 0

    for schedule in schedules:
        try:
            if _materialize_schedule(session, schedule, current_time):
                materialized += 1
            else:
                skipped += 1
            session.flush()
        except IntegrityError:
            session.rollback()
            failed += 1
            break
        except Exception as exc:  # preserve a ledger entry for operational diagnosis
            session.add(
                ScheduleRun(
                    schedule_id=schedule.id,
                    scheduled_for=schedule.next_run_at or current_time,
                    status="failed",
                    error=str(exc)[:2000],
                )
            )
            failed += 1

    session.commit()
    return SchedulerTickResult(
        inspected=len(schedules),
        materialized=materialized,
        skipped=skipped,
        failed=failed,
    )
