from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.settings import settings

_password_hasher = PasswordHasher()


class TokenError(ValueError):
    """Raised when a signed token is invalid or expired."""


@dataclass(frozen=True)
class IssuedToken:
    token: str
    expires_at: int


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(secret: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(secret), expected_hash)


def generate_secret(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(32)}"


def issue_token(subject: str, token_type: str, ttl_seconds: int, **claims: Any) -> IssuedToken:
    now = int(time.time())
    expires_at = now + ttl_seconds
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": expires_at, **claims}
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(encoded_payload)
    return IssuedToken(token=f"{encoded_payload}.{signature}", expires_at=expires_at)


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise TokenError("Malformed token") from exc

    if not hmac.compare_digest(signature, _sign(encoded_payload)):
        raise TokenError("Invalid token signature")

    try:
        payload = json.loads(_b64decode(encoded_payload))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("Invalid token payload") from exc

    if int(payload.get("exp", 0)) <= int(time.time()):
        raise TokenError("Token expired")
    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError("Unexpected token type")
    return payload


def _sign(encoded_payload: str) -> str:
    digest = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64encode(digest)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
