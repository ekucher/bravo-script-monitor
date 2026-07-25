import time

import pytest

from app.auth.security import (
    TokenError,
    decode_token,
    generate_secret,
    hash_password,
    hash_secret,
    issue_token,
    verify_password,
    verify_secret,
)


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_secret_hash_round_trip() -> None:
    secret = generate_secret("bsm")

    assert secret.startswith("bsm_")
    assert verify_secret(secret, hash_secret(secret))
    assert not verify_secret(f"{secret}x", hash_secret(secret))


def test_access_token_round_trip() -> None:
    issued = issue_token("user-id", "access", 60, permissions=["organizations.read"])
    payload = decode_token(issued.token, expected_type="access")

    assert payload["sub"] == "user-id"
    assert payload["permissions"] == ["organizations.read"]


def test_token_type_is_enforced() -> None:
    token = issue_token("user-id", "refresh", 60).token

    with pytest.raises(TokenError, match="Unexpected token type"):
        decode_token(token, expected_type="access")


def test_expired_token_is_rejected() -> None:
    token = issue_token("user-id", "access", -1).token
    time.sleep(0.01)

    with pytest.raises(TokenError, match="Token expired"):
        decode_token(token, expected_type="access")
