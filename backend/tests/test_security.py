"""
安全模块单元测试

覆盖重点：
- bcrypt 哈希与校验
- Access/Refresh Token 签发字段
- Token 过期与非法格式
"""
from __future__ import annotations

from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_should_not_equal_plain_text() -> None:
    plain = "TestPass123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True


def test_verify_password_should_fail_for_wrong_password() -> None:
    hashed = hash_password("RightPass123")
    assert verify_password("WrongPass123", hashed) is False


def test_create_access_token_should_include_required_claims() -> None:
    token = create_access_token({"user_id": 1, "role": "client", "token_version": 3})
    payload = decode_token(token)

    assert payload["user_id"] == 1
    assert payload["role"] == "client"
    assert payload["token_version"] == 3
    assert payload["type"] == "access"
    assert isinstance(payload.get("jti"), str)
    assert payload.get("exp") is not None


def test_create_refresh_token_should_be_refresh_type() -> None:
    token = create_refresh_token({"user_id": 100})
    payload = decode_token(token)

    assert payload["user_id"] == 100
    assert payload["type"] == "refresh"
    assert payload.get("exp") is not None
    assert "jti" not in payload


def test_decode_token_should_raise_when_expired() -> None:
    expired_token = create_access_token(
        {"user_id": 1, "role": "client", "token_version": 1},
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)


def test_decode_token_should_raise_for_invalid_token() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_token("not-a-valid-jwt")
