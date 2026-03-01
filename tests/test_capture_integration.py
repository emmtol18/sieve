from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


MOCK_LLM_RESULT = {
    "title": "Test Capsule",
    "executive_summary": "A test summary",
    "core_insight": "A test insight",
    "tags": ["test", "mock"],
    "keywords": ["testing"],
    "topics": ["Software Testing"],
    "category": "Technology",
    "domain": "engineering",
    "difficulty": "beginner",
    "content_type": "insight",
    "source_type": "article",
}


@pytest.fixture
def mock_llm():
    with patch("sieve.api.capture.pipeline.LLMClient") as mock_cls:
        instance = mock_cls.return_value
        result = {**MOCK_LLM_RESULT, "full_content": "Some test content"}
        instance.extract_capsule = AsyncMock(return_value=result)
        yield instance


@pytest.fixture
def mock_fetch_url():
    with patch("sieve.api.capture.pipeline.fetch_url", new_callable=AsyncMock) as mock:
        mock.return_value = "<html><body><p>Fetched content</p></body></html>"
        yield mock


async def test_capture_text_authenticated(client, test_user, auth_cookies, mock_llm):
    """POST text content with auth cookie returns 201 and created capsule."""
    response = await client.post(
        "/api/capture/",
        json={"content": "Some knowledge to capture"},
        cookies=auth_cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Capsule"
    assert data["capture_method"] == "manual"
    mock_llm.extract_capsule.assert_called_once()


async def test_capture_url_authenticated(client, test_user, auth_cookies, mock_llm, mock_fetch_url):
    """POST URL with auth cookie returns 201 with source_url set."""
    response = await client.post(
        "/api/capture/",
        json={"url": "https://example.com/article"},
        cookies=auth_cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Capsule"
    assert data["source_url"] == "https://example.com/article"
    assert data["capture_method"] == "url"
    mock_fetch_url.assert_called_once_with("https://example.com/article")


async def test_capture_unauthenticated(client):
    """POST without auth cookie returns 401."""
    response = await client.post(
        "/api/capture/",
        json={"content": "Some content"},
    )
    assert response.status_code == 401


async def test_capture_empty_content(client, test_user, auth_cookies, mock_llm):
    """POST with empty content and no URL returns 400."""
    response = await client.post(
        "/api/capture/",
        json={"content": ""},
        cookies=auth_cookies,
    )
    assert response.status_code == 400


async def test_capture_localhost_url(client, test_user, auth_cookies):
    """POST with localhost URL returns 400 (SSRF protection)."""
    response = await client.post(
        "/api/capture/",
        json={"url": "http://localhost/secret"},
        cookies=auth_cookies,
    )
    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()


async def test_capture_llm_failure(app, test_user, auth_cookies):
    """POST when LLM raises results in an unhandled server error."""
    with patch("sieve.api.capture.pipeline.LLMClient") as mock_cls:
        instance = mock_cls.return_value
        instance.extract_capsule = AsyncMock(side_effect=Exception("LLM is down"))
        # Use raise_app_exceptions=False so unhandled errors become 500 responses
        # instead of propagating as Python exceptions through the ASGI transport.
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post(
                "/api/capture/",
                json={"content": "Some content"},
                cookies=auth_cookies,
            )
    assert response.status_code == 500


async def test_capture_persists_to_db(client, test_user, auth_cookies, mock_llm, db_session):
    """Captured capsule is persisted to database with correct fields."""
    from sqlalchemy import select
    from sieve.db.models import Capsule

    response = await client.post(
        "/api/capture/",
        json={"content": "Persist this knowledge"},
        cookies=auth_cookies,
    )
    assert response.status_code == 201
    capsule_id = response.json()["id"]

    # Need to get a fresh session since the client uses its own session
    result = await db_session.execute(select(Capsule).where(Capsule.id == capsule_id))
    capsule = result.scalar_one_or_none()
    assert capsule is not None
    assert capsule.title == "Test Capsule"
    assert capsule.category == "Technology"
