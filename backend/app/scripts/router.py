from hashlib import sha256
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db_session
from app.models import Organization, Script, ScriptVersion
from app.scripts.schemas import (
    ScriptCreate,
    ScriptRead,
    ScriptUpdate,
    ScriptVersionCreate,
    ScriptVersionRead,
    ScriptVersionSummary,
)

DbSession = Annotated[Session, Depends(get_db_session)]
router = APIRouter(prefix="/scripts", tags=["scripts"])


def _get_script_or_404(session: Session, script_id: UUID) -> Script:
    script = session.get(Script, script_id)
    if script is None:
        raise HTTPException(status_code=404, detail="Script not found")
    return script


def _get_version_or_404(session: Session, script_id: UUID, version: str) -> ScriptVersion:
    item = session.scalar(
        select(ScriptVersion).where(
            ScriptVersion.script_id == script_id,
            ScriptVersion.version == version,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Script version not found")
    return item


@router.get(
    "",
    response_model=list[ScriptRead],
    dependencies=[Depends(require_permission("scripts.read"))],
)
def list_scripts(
    session: DbSession,
    organization_id: UUID | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Script]:
    statement = select(Script).order_by(Script.name)
    if organization_id is not None:
        statement = statement.where(Script.organization_id == organization_id)
    if search is not None:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            func.lower(Script.name).like(func.lower(pattern))
            | func.lower(func.coalesce(Script.description, "")).like(func.lower(pattern))
        )
    return list(session.scalars(statement.offset(offset).limit(limit)))


@router.post(
    "",
    response_model=ScriptRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("scripts.write"))],
)
def create_script(payload: ScriptCreate, session: DbSession) -> Script:
    if session.get(Organization, payload.organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    script = Script(**payload.model_dump())
    session.add(script)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Script name already exists in this organization",
        ) from exc
    session.refresh(script)
    return script


@router.get(
    "/{script_id}",
    response_model=ScriptRead,
    dependencies=[Depends(require_permission("scripts.read"))],
)
def get_script(script_id: UUID, session: DbSession) -> Script:
    return _get_script_or_404(session, script_id)


@router.patch(
    "/{script_id}",
    response_model=ScriptRead,
    dependencies=[Depends(require_permission("scripts.write"))],
)
def update_script(script_id: UUID, payload: ScriptUpdate, session: DbSession) -> Script:
    script = _get_script_or_404(session, script_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(script, field, value)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Script name already exists in this organization",
        ) from exc
    session.refresh(script)
    return script


@router.delete(
    "/{script_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_permission("scripts.write"))],
)
def delete_script(script_id: UUID, session: DbSession) -> Response:
    script = _get_script_or_404(session, script_id)
    if script.versions:
        raise HTTPException(status_code=409, detail="Delete script versions before deleting the script")
    session.delete(script)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{script_id}/versions",
    response_model=list[ScriptVersionSummary],
    dependencies=[Depends(require_permission("scripts.read"))],
)
def list_script_versions(script_id: UUID, session: DbSession) -> list[ScriptVersion]:
    _get_script_or_404(session, script_id)
    statement = (
        select(ScriptVersion)
        .where(ScriptVersion.script_id == script_id)
        .order_by(ScriptVersion.created_at.desc())
    )
    return list(session.scalars(statement))


@router.post(
    "/{script_id}/versions",
    response_model=ScriptVersionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("scripts.write"))],
)
def create_script_version(
    script_id: UUID,
    payload: ScriptVersionCreate,
    session: DbSession,
) -> ScriptVersion:
    _get_script_or_404(session, script_id)
    metadata = dict(payload.parameter_schema)
    repository_metadata = dict(metadata.get("_repository", {}))
    repository_metadata.update({"language": payload.language, "published": False})
    metadata["_repository"] = repository_metadata
    version = ScriptVersion(
        script_id=script_id,
        version=payload.version,
        content=payload.content,
        sha256=sha256(payload.content.encode("utf-8")).hexdigest(),
        parameter_schema=metadata,
    )
    session.add(version)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Script version already exists") from exc
    session.refresh(version)
    return version


@router.get(
    "/{script_id}/versions/{version}",
    response_model=ScriptVersionRead,
    dependencies=[Depends(require_permission("scripts.read"))],
)
def get_script_version(script_id: UUID, version: str, session: DbSession) -> ScriptVersion:
    _get_script_or_404(session, script_id)
    return _get_version_or_404(session, script_id, version)


@router.post(
    "/{script_id}/versions/{version}/publish",
    response_model=ScriptVersionRead,
    dependencies=[Depends(require_permission("scripts.publish"))],
)
def publish_script_version(script_id: UUID, version: str, session: DbSession) -> ScriptVersion:
    _get_script_or_404(session, script_id)
    item = _get_version_or_404(session, script_id, version)
    metadata = dict(item.parameter_schema)
    repository_metadata = dict(metadata.get("_repository", {}))
    repository_metadata["published"] = True
    metadata["_repository"] = repository_metadata
    item.parameter_schema = metadata
    session.commit()
    session.refresh(item)
    return item
