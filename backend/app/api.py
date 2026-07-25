from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db_session
from app.models import Installation, Organization
from app.schemas import (
    InstallationCreate,
    InstallationRead,
    OrganizationCreate,
    OrganizationRead,
)

APP_VERSION = "0.2.0-alpha"
DbSession = Annotated[Session, Depends(get_db_session)]

router = APIRouter(prefix="/api/v1")
system_router = APIRouter(tags=["system"])
organization_router = APIRouter(prefix="/organizations", tags=["organizations"])
installation_router = APIRouter(prefix="/installations", tags=["installations"])


@system_router.get("/health", summary="Check API health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@system_router.get("/live", include_in_schema=False)
def live() -> dict[str, str]:
    return health()


@system_router.get("/ready", summary="Check API readiness")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@system_router.get("/version", summary="Get component version")
def version() -> dict[str, str]:
    return {
        "component": "bsm-backend",
        "version": APP_VERSION,
        "api_version": "v1",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@organization_router.get("", response_model=list[OrganizationRead])
def list_organizations(
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Organization]:
    statement = select(Organization).order_by(Organization.name).offset(offset).limit(limit)
    return list(session.scalars(statement))


@organization_router.post(
    "",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(payload: OrganizationCreate, session: DbSession) -> Organization:
    organization = Organization(**payload.model_dump())
    session.add(organization)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Organization slug already exists") from exc
    session.refresh(organization)
    return organization


@installation_router.get("", response_model=list[InstallationRead])
def list_installations(
    session: DbSession,
    organization_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Installation]:
    statement = select(Installation).order_by(Installation.name)
    if organization_id is not None:
        statement = statement.where(Installation.organization_id == organization_id)
    statement = statement.offset(offset).limit(limit)
    return list(session.scalars(statement))


@installation_router.post(
    "",
    response_model=InstallationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_installation(payload: InstallationCreate, session: DbSession) -> Installation:
    organization = session.get(Organization, payload.organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    installation = Installation(**payload.model_dump())
    session.add(installation)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Installation code already exists in this organization",
        ) from exc
    session.refresh(installation)
    return installation


router.include_router(system_router)
router.include_router(organization_router)
router.include_router(installation_router)
