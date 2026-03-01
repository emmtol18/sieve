import uuid

from unittest.mock import AsyncMock
from fastapi import Request

from sieve.api.auth.deps import (
    create_access_token,
    get_token_from_request,
    hash_password,
    verify_password,
    verify_token,
)


def test_password_hashing():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    user_id = uuid.uuid4()
    token = create_access_token(str(user_id))
    decoded_id = verify_token(token)
    assert decoded_id == str(user_id)


def test_jwt_invalid_token():
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        verify_token("invalid-token")
    assert exc.value.status_code == 401


def test_get_token_from_cookie():
    """Token extracted from sieve_token cookie."""
    request = AsyncMock(spec=Request)
    request.cookies = {"sieve_token": "my-jwt-token"}
    request.headers = {}
    assert get_token_from_request(request) == "my-jwt-token"


def test_get_token_from_bearer_header():
    """Falls back to Authorization Bearer header."""
    request = AsyncMock(spec=Request)
    request.cookies = {}
    request.headers = {"authorization": "Bearer my-jwt-token"}
    assert get_token_from_request(request) == "my-jwt-token"


def test_get_token_cookie_takes_precedence():
    """Cookie wins over header when both present."""
    request = AsyncMock(spec=Request)
    request.cookies = {"sieve_token": "cookie-token"}
    request.headers = {"authorization": "Bearer header-token"}
    assert get_token_from_request(request) == "cookie-token"


def test_get_token_missing_returns_none():
    """Returns None when neither cookie nor header present."""
    request = AsyncMock(spec=Request)
    request.cookies = {}
    request.headers = {}
    assert get_token_from_request(request) is None


def test_set_auth_cookie_creates_response_with_cookie():
    """set_auth_cookie sets httponly sieve_token cookie."""
    from fastapi.responses import JSONResponse
    from sieve.api.auth.routes import set_auth_cookie

    response = JSONResponse(content={"ok": True})
    set_auth_cookie(response, "test-jwt-token", max_age_days=7)

    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "sieve_token=test-jwt-token" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "path=/" in set_cookie.lower()
