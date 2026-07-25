from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser
from app.auth.models import ApiKey, RefreshToken, User
from app.auth.schemas import ApiKeyCreate, ApiKeyCreated, LoginRequest, RefreshRequest, TokenPair, UserRead
from app.auth.security import (
    TokenError,
    decode_token,
    generate_secret,
    hash_secret,
    issue_token,
    verify_password,
)
from app.database import get_db_session
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _create_token_pair(session: Session, user: User) -> TokenPair:
    access = issue_token(
        str(user.id),
        "access",
        settings.access_token_ttl_seconds,
        permissions=user.permissions,
        superuser=user.is_superuser,
    )
    refresh = issue_token(str(user.id), "refresh", settings.refresh_token_ttl_seconds)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_secret(refresh.token),
            expires_at=datetime.fromtimestamp(refresh.expires_at, UTC),
        )
    )
    session.commit()
    return TokenPair(
        access_token=access.token,
        refresh_token=refresh.token,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, session: DbSession) -> TokenPair:
    user = session.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return _create_token_pair(session, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, session: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    stored = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_secret(payload.refresh_token))
    )
    if stored is None or stored.revoked_at is not None or stored.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
    user = session.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    stored.revoked_at = datetime.now(UTC)
    session.commit()
    return _create_token_pair(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, session: DbSession) -> None:
    stored = session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_secret(payload.refresh_token))
    )
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        session.commit()


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(payload: ApiKeyCreate, user: CurrentUser, session: DbSession) -> ApiKeyCreated:
    raw_key = generate_secret("bsm")
    record = ApiKey(
        owner_type="user",
        owner_id=str(user.id),
        name=payload.name,
        key_prefix=raw_key[:16],
        key_hash=hash_secret(raw_key),
        permissions=payload.permissions,
        expires_at=payload.expires_at,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return ApiKeyCreated(
        id=record.id,
        name=record.name,
        key=raw_key,
        key_prefix=record.key_prefix,
        permissions=record.permissions,
        expires_at=record.expires_at,
    )
