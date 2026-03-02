"""Tests for Google OAuth signup with username generation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sieve.api.auth.deps import hash_password
from sieve.api.auth.google import _generate_unique_username, _sanitize_username
from sieve.db.models import Sieve, User


@pytest.fixture
def google_configured(monkeypatch):
    """Set Google OAuth credentials in settings."""
    monkeypatch.setenv("SIEVE_GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SIEVE_GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("SIEVE_GOOGLE_REDIRECT_URI", "http://test/auth/google/callback")
    # Reload settings so env vars take effect
    from sieve.config import Settings

    new_settings = Settings()
    monkeypatch.setattr("sieve.api.auth.google.settings", new_settings)


def test_sanitize_username_basic():
    """Sanitize simple email prefix."""
    assert _sanitize_username("john") == "john"


def test_sanitize_username_with_dots():
    """Dots converted to underscores."""
    assert _sanitize_username("john.doe") == "john_doe"


def test_sanitize_username_with_special_chars():
    """Special characters converted to underscores."""
    assert _sanitize_username("john+tag") == "john_tag"


def test_sanitize_username_short():
    """Short strings get padded to minimum 3 chars."""
    result = _sanitize_username("ab")
    assert len(result) >= 3
    assert result == "ab_user"


def test_sanitize_username_uppercase():
    """Uppercase converted to lowercase."""
    assert _sanitize_username("JohnDoe") == "johndoe"


def test_sanitize_username_consecutive_special():
    """Consecutive special chars collapse to single underscore."""
    assert _sanitize_username("john...doe") == "john_doe"


async def test_generate_unique_username_available(db_session):
    """When base username is available, use it directly."""
    username = await _generate_unique_username("john@example.com", db_session)
    assert username == "john"


async def test_generate_unique_username_taken(db_session, test_user):
    """When base username is taken, append a random suffix."""
    # test_user has username "testuser"
    username = await _generate_unique_username("testuser@example.com", db_session)
    assert username.startswith("testuser_")
    assert username != "testuser"
    assert len(username) >= 3


async def test_google_login_redirects(client, google_configured):
    """GET /auth/google/login redirects to accounts.google.com."""
    response = await client.get("/auth/google/login", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert "accounts.google.com" in location


async def test_google_login_501_when_not_configured(client):
    """GET /auth/google/login returns 501 when client_id is empty."""
    response = await client.get("/auth/google/login")
    assert response.status_code == 501


@patch("sieve.api.auth.google.AsyncOAuth2Client")
async def test_google_callback_creates_user_with_username(
    mock_oauth_cls, client, db_session, google_configured
):
    """Google callback creates a new user with oauth_provider='google' and a generated username."""
    mock_client = AsyncMock()
    mock_oauth_cls.return_value = mock_client

    mock_client.fetch_token = AsyncMock(return_value={"access_token": "fake"})
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "email": "googleuser@example.com",
        "name": "Google User",
        "sub": "12345",
    }
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.aclose = AsyncMock()

    response = await client.get(
        "/auth/google/callback?code=test-code", follow_redirects=False
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/sieve"
    assert "sieve_token" in response.headers.get("set-cookie", "")

    # Verify user was created with username and oauth_provider
    from sqlalchemy import select

    result = await db_session.execute(
        select(User).where(User.email == "googleuser@example.com")
    )
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.display_name == "Google User"
    assert user.oauth_provider == "google"
    assert user.password_hash is None
    assert user.username == "googleuser"


@patch("sieve.api.auth.google.AsyncOAuth2Client")
async def test_google_callback_existing_user(
    mock_oauth_cls, client, db_session, google_configured
):
    """Google callback logs in existing user without creating duplicate."""
    # Pre-create user
    user = User(
        email="existing@example.com",
        password_hash=hash_password("password"),
        display_name="Existing User",
        username="existing",
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Test Sieve")
    db_session.add(sieve)
    await db_session.commit()

    mock_client = AsyncMock()
    mock_oauth_cls.return_value = mock_client
    mock_client.fetch_token = AsyncMock(return_value={"access_token": "fake"})
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "email": "existing@example.com",
        "name": "Existing User",
        "sub": "12345",
    }
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.aclose = AsyncMock()

    response = await client.get(
        "/auth/google/callback?code=test-code", follow_redirects=False
    )
    assert response.status_code == 302
    assert "sieve_token" in response.headers.get("set-cookie", "")

    # Verify no duplicate
    from sqlalchemy import func, select

    result = await db_session.execute(
        select(func.count()).where(User.email == "existing@example.com")
    )
    assert result.scalar() == 1


async def test_password_login_rejects_oauth_user(client, db_session):
    """Password login for OAuth-only user (no password_hash) returns 401, not 500."""
    user = User(
        email="oauth_only@example.com",
        password_hash=None,
        display_name="OAuth Only",
        oauth_provider="google",
        username="oauth_only",
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="OAuth Sieve")
    db_session.add(sieve)
    await db_session.commit()

    # API login
    response = await client.post(
        "/api/auth/login",
        json={"email": "oauth_only@example.com", "password": "anything"},
    )
    assert response.status_code == 401

    # HTMX login
    response = await client.post(
        "/htmx/auth/login",
        data={"email": "oauth_only@example.com", "password": "anything"},
    )
    assert response.status_code == 200
    assert "Invalid email or password" in response.text
