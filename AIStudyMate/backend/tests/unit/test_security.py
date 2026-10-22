from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.common import UserRole


def test_password_is_hashed_and_verifiable() -> None:
    password = "StrongPassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_access_and_refresh_tokens_have_distinct_types() -> None:
    user_id = uuid4()
    access_token = create_access_token(user_id, UserRole.STUDENT)
    refresh_token = create_refresh_token(user_id, UserRole.STUDENT)

    access_payload = decode_token(access_token, TokenType.ACCESS)
    refresh_payload = decode_token(refresh_token, TokenType.REFRESH)

    assert access_payload["sub"] == str(user_id)
    assert access_payload["role"] == UserRole.STUDENT.value
    assert refresh_payload["sub"] == str(user_id)
    assert access_payload["jti"] != refresh_payload["jti"]


def test_refresh_token_cannot_be_used_as_access_token() -> None:
    token = create_refresh_token(uuid4(), UserRole.STUDENT)

    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS)


def test_expired_token_is_rejected() -> None:
    token = create_token(
        user_id=uuid4(),
        role=UserRole.STUDENT,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(InvalidTokenError):
        decode_token(token, TokenType.ACCESS)

