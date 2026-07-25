from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.dependencies import CurrentAgent
from app.agents.schemas import (
    AgentHeartbeatRequest,
    AgentInventoryRequest,
    AgentJobRead,
    AgentJobResultRequest,
    AgentRead,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
)
from app.auth.dependencies import require_permission
from app.auth.security import generate_secret, hash_secret
from app.database import get_db_session
from app.models import Agent, AgentStatus, Execution, Installation, Job, JobStatus, ScriptVersion, Server

DbSession = Annotated[Session, Depends(get_db_session)]

router = APIRouter(prefix="/agents", tags=["agents"])
agent_api_router = APIRouter(prefix="/self")


@router.get(
    "",
    response_model=list[AgentRead],
    dependencies=[Depends(require_permission("agents.read"))],
)
def list_agents(
    session: DbSession,
    installation_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Agent]:
    statement = select(Agent).join(Agent.server).order_by(Agent.created_at.desc())
    if installation_id is not None:
        statement = statement.where(Server.installation_id == installation_id)
    return list(session.scalars(statement.offset(offset).limit(limit)))


@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("agents.write"))],
)
def register_agent(payload: AgentRegistrationRequest, session: DbSession) -> AgentRegistrationResponse:
    installation = session.get(Installation, payload.installation_id)
    if installation is None:
        raise HTTPException(status_code=404, detail="Installation not found")

    server = session.scalar(
        select(Server).where(
            Server.installation_id == payload.installation_id,
            Server.hostname == payload.hostname,
        )
    )
    if server is None:
        server = Server(
            installation_id=payload.installation_id,
            hostname=payload.hostname,
            operating_system=payload.operating_system,
            inventory=payload.inventory,
        )
        session.add(server)
        session.flush()
    else:
        server.operating_system = payload.operating_system or server.operating_system
        if payload.inventory:
            server.inventory = payload.inventory

    existing = session.scalar(
        select(Agent).where(Agent.server_id == server.id, Agent.name == payload.agent_name)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="Agent already registered for this server")

    raw_token = generate_secret("bsm_agent")
    now = datetime.now(UTC)
    agent = Agent(
        server_id=server.id,
        name=payload.agent_name,
        version=payload.version,
        status=AgentStatus.online,
        last_seen_at=now,
        capabilities=payload.capabilities,
        token_hash=hash_secret(raw_token),
    )
    session.add(agent)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Agent registration conflict") from exc
    session.refresh(agent)
    return AgentRegistrationResponse(
        agent_id=agent.id,
        token=raw_token,
        status=agent.status,
        registered_at=agent.created_at,
    )


@agent_api_router.post("/heartbeat", response_model=AgentRead)
def heartbeat(payload: AgentHeartbeatRequest, agent: CurrentAgent, session: DbSession) -> Agent:
    agent.last_seen_at = datetime.now(UTC)
    agent.status = AgentStatus.online
    if payload.version is not None:
        agent.version = payload.version
    if payload.capabilities is not None:
        agent.capabilities = payload.capabilities
    session.commit()
    session.refresh(agent)
    return agent


@agent_api_router.put(
    "/inventory",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def update_inventory(
    payload: AgentInventoryRequest,
    agent: CurrentAgent,
    session: DbSession,
) -> Response:
    server = session.get(Server, agent.server_id)
    if server is None:
        raise HTTPException(status_code=409, detail="Agent server no longer exists")
    server.operating_system = payload.operating_system or server.operating_system
    server.inventory = payload.inventory
    agent.last_seen_at = datetime.now(UTC)
    agent.status = AgentStatus.online
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@agent_api_router.post("/jobs/claim", response_model=AgentJobRead | None)
def claim_job(agent: CurrentAgent, session: DbSession) -> AgentJobRead | None:
    now = datetime.now(UTC)
    statement = (
        select(Job)
        .where(
            Job.agent_id == agent.id,
            Job.status.in_([JobStatus.pending, JobStatus.queued]),
            or_(Job.scheduled_for.is_(None), Job.scheduled_for <= now),
        )
        .order_by(Job.scheduled_for.asc().nullsfirst(), Job.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = session.scalar(statement)
    if job is None:
        agent.last_seen_at = now
        agent.status = AgentStatus.online
        session.commit()
        return None

    version = session.get(ScriptVersion, job.script_version_id)
    if version is None:
        job.status = JobStatus.failed
        session.commit()
        raise HTTPException(status_code=409, detail="Job script version no longer exists")

    job.status = JobStatus.running
    execution = Execution(
        job_id=job.id,
        attempt=len(job.executions) + 1,
        status=JobStatus.running,
        started_at=now,
    )
    session.add(execution)
    agent.last_seen_at = now
    agent.status = AgentStatus.online
    session.commit()
    return AgentJobRead(
        id=job.id,
        status=job.status,
        script_version_id=version.id,
        parameters=job.parameters,
        scheduled_for=job.scheduled_for,
        script=version.content,
        script_sha256=version.sha256,
    )


@agent_api_router.post(
    "/jobs/{job_id}/result",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def submit_job_result(
    job_id: UUID,
    payload: AgentJobResultRequest,
    agent: CurrentAgent,
    session: DbSession,
) -> Response:
    if payload.status not in {JobStatus.succeeded, JobStatus.failed, JobStatus.cancelled}:
        raise HTTPException(status_code=422, detail="Result status must be terminal")

    job = session.get(Job, job_id)
    if job is None or job.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Job not found")
    execution = session.scalar(
        select(Execution).where(Execution.job_id == job.id).order_by(Execution.attempt.desc()).limit(1)
    )
    if execution is None:
        raise HTTPException(status_code=409, detail="Job has no active execution")

    now = datetime.now(UTC)
    execution.status = payload.status
    execution.exit_code = payload.exit_code
    execution.stdout = payload.stdout
    execution.stderr = payload.stderr
    execution.started_at = payload.started_at or execution.started_at
    execution.finished_at = payload.finished_at or now
    job.status = payload.status
    agent.last_seen_at = now
    agent.status = AgentStatus.online
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


router.include_router(agent_api_router)
