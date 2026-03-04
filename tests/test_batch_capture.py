import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from sieve.api.auth.deps import create_access_token, hash_password
from sieve.api.capsules.schemas import BatchCaptureItem, BatchCaptureRequest
from sieve.db.models import Creator, Sieve, User


def test_batch_capture_item_schema():
    item = BatchCaptureItem(content="tweet text", source_url="https://x.com/user/status/123")
    assert item.content == "tweet text"
    assert item.source_url == "https://x.com/user/status/123"


def test_batch_capture_item_source_url_optional():
    item = BatchCaptureItem(content="tweet text")
    assert item.source_url is None


def test_batch_capture_request_schema():
    req = BatchCaptureRequest(
        items=[
            BatchCaptureItem(content="tweet 1"),
            BatchCaptureItem(content="tweet 2"),
        ],
        creator_id="abc-123",
    )
    assert len(req.items) == 2
    assert req.creator_id == "abc-123"
    assert req.source_type == "tweet"


def test_batch_capture_request_source_type_default():
    req = BatchCaptureRequest(
        items=[BatchCaptureItem(content="tweet")],
        creator_id="abc",
    )
    assert req.source_type == "tweet"


@pytest.fixture
async def admin_user(db_session):
    user = User(
        email="admin@example.com",
        password_hash=hash_password("adminpassword"),
        display_name="Admin User",
        username="admin",
        is_admin=True,
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Admin Sieve")
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def admin_cookies(admin_user):
    return {"sieve_token": create_access_token(str(admin_user.id))}


@pytest.fixture
async def creator(db_session):
    c = Creator(
        id=uuid.uuid4(),
        name="Test Creator",
        slug="test-creator",
        description="Test",
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest.mark.asyncio
async def test_batch_capture_success(app, admin_cookies, creator):
    mock_result = {
        "title": "Extracted Title",
        "executive_summary": "Summary",
        "core_insight": "Insight",
        "full_content": "Content",
        "tags": ["ai"],
        "keywords": ["ml"],
        "topics": ["tech"],
        "category": "AI",
        "domain": "Technology",
        "difficulty": "intermediate",
        "content_type": "insight",
        "author": "test",
        "source_url": None,
        "capture_method": "manual",
        "source_type": "tweet",
    }

    with patch(
        "sieve.api.capture.routes.CapturePipeline.process",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/capture/batch",
                json={
                    "items": [
                        {"content": "tweet one"},
                        {"content": "tweet two"},
                    ],
                    "creator_id": str(creator.id),
                },
                cookies=admin_cookies,
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["succeeded"] == 2
    assert body["failed"] == 0
    assert len(body["results"]) == 2
    assert all(r["status"] == "success" for r in body["results"])


@pytest.mark.asyncio
async def test_batch_capture_rejects_non_admin(app, db_session, creator):
    user = User(
        email="regular@example.com",
        password_hash=hash_password("password"),
        display_name="Regular User",
        username="regular",
        is_admin=False,
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Regular Sieve")
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/capture/batch",
            json={
                "items": [{"content": "tweet"}],
                "creator_id": str(creator.id),
            },
            cookies={"sieve_token": token},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_batch_capture_creator_not_found(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/capture/batch",
            json={
                "items": [{"content": "tweet"}],
                "creator_id": str(uuid.uuid4()),
            },
            cookies=admin_cookies,
        )
    assert resp.status_code == 404
