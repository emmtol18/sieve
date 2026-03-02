from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sieve.api.auth.deps import hash_password
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
async def test_google_callback_creates_user(mock_oauth_cls, client, db_session, google_configured):
    """Google callback creates a new user with oauth_provider='google'."""
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

    # Verify user was created
    from sqlalchemy import select

    result = await db_session.execute(
        select(User).where(User.email == "googleuser@example.com")
    )
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.display_name == "Google User"
    assert user.oauth_provider == "google"
    assert user.password_hash is None


@patch("sieve.api.auth.google.AsyncOAuth2Client")
async def test_google_callback_existing_user(mock_oauth_cls, client, db_session, google_configured):
    """Google callback logs in existing user without creating duplicate."""
    # Pre-create user
    user = User(
        email="existing@example.com",
        password_hash=hash_password("password"),
        display_name="Existing User",
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
