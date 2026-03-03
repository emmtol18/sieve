import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from sieve.api.auth.deps import create_access_token, hash_password
from sieve.api.capsules.schemas import CaptureRequest
from sieve.api.leaders.schemas import (
    LeaderCreate,
    LeaderListResponse,
    LeaderResponse,
    LeaderUpdate,
)
from sieve.db.models import Leader, Sieve, User


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


def test_leader_model_instantiation():
    leader = Leader(
        id=uuid.uuid4(),
        name="Andrej Karpathy",
        slug="karpathy",
        description="AI researcher and educator",
        bio="Former Tesla AI Director",
        expertise_domain="AI",
        avatar_url="https://example.com/avatar.jpg",
        twitter_url="https://twitter.com/karpathy",
        linkedin_url="https://linkedin.com/in/karpathy",
        author_url="https://karpathy.ai",
        topics=["ai", "deep-learning"],
        is_featured=True,
        capsule_count=42,
    )
    assert leader.name == "Andrej Karpathy"
    assert leader.slug == "karpathy"
    assert leader.bio == "Former Tesla AI Director"
    assert leader.expertise_domain == "AI"
    assert leader.avatar_url == "https://example.com/avatar.jpg"
    assert leader.twitter_url == "https://twitter.com/karpathy"
    assert leader.linkedin_url == "https://linkedin.com/in/karpathy"
    assert leader.is_featured is True
    assert leader.capsule_count == 42
    assert "ai" in leader.topics


def test_leader_defaults():
    leader = Leader(
        id=uuid.uuid4(),
        name="Minimal Leader",
        slug="minimal",
        description="A minimal leader entry",
    )
    assert leader.is_featured is False
    assert leader.capsule_count == 0
    assert leader.rating_avg == 0.0
    assert leader.review_count == 0


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_leader_create_schema():
    data = LeaderCreate(
        name="Test Leader",
        slug="test-leader",
        description="Test description",
        bio="Test bio",
        expertise_domain="Testing",
    )
    assert data.name == "Test Leader"
    assert data.slug == "test-leader"
    assert data.bio == "Test bio"
    assert data.expertise_domain == "Testing"
    assert data.topics == []
    assert data.is_featured is False
    assert data.avatar_url is None


def test_leader_create_schema_defaults():
    data = LeaderCreate(
        name="Minimal",
        slug="minimal",
        description="Minimal description",
    )
    assert data.bio == ""
    assert data.expertise_domain == ""
    assert data.avatar_url is None
    assert data.twitter_url is None
    assert data.linkedin_url is None
    assert data.author_url is None
    assert data.topics == []
    assert data.is_featured is False


def test_leader_update_schema_partial():
    data = LeaderUpdate(name="Updated Name")
    dumped = data.model_dump(exclude_unset=True)
    assert dumped == {"name": "Updated Name"}


def test_leader_update_schema_empty():
    data = LeaderUpdate()
    dumped = data.model_dump(exclude_unset=True)
    assert dumped == {}


def test_leader_response_schema():
    resp = LeaderResponse(
        id="abc-123",
        name="Test",
        slug="test",
        description="Desc",
        bio="Bio",
        expertise_domain="Tech",
        avatar_url=None,
        twitter_url=None,
        linkedin_url=None,
        author_url=None,
        topics=["ai"],
        is_featured=True,
        capsule_count=5,
        created_at="2026-01-01T00:00:00+00:00",
    )
    assert resp.id == "abc-123"
    assert resp.is_featured is True
    assert resp.capsule_count == 5


def test_leader_list_response_schema():
    resp = LeaderListResponse(leaders=[], total=0)
    assert resp.total == 0
    assert resp.leaders == []


# ---------------------------------------------------------------------------
# require_admin tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_admin_rejects_non_admin(app, db_session):
    """Non-admin users receive 403 on admin-only endpoints."""
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
            "/api/leaders/",
            json={
                "name": "Hacker",
                "slug": "hacker",
                "description": "Should fail",
            },
            cookies={"sieve_token": token},
        )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required"


@pytest.mark.asyncio
async def test_require_admin_rejects_unauthenticated(app):
    """Unauthenticated requests receive 401 on admin-only endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/leaders/",
            json={
                "name": "Anon",
                "slug": "anon",
                "description": "Should fail",
            },
        )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# API route tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_user(db_session):
    """Create an admin user with a sieve."""
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
    token = create_access_token(str(admin_user.id))
    return {"sieve_token": token}


@pytest.mark.asyncio
async def test_create_leader(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/leaders/",
            json={
                "name": "Andrej Karpathy",
                "slug": "karpathy",
                "description": "AI researcher",
                "bio": "Former Tesla AI Director",
                "expertise_domain": "AI",
            },
            cookies=admin_cookies,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Andrej Karpathy"
    assert body["slug"] == "karpathy"
    assert body["bio"] == "Former Tesla AI Director"
    assert body["expertise_domain"] == "AI"
    assert body["is_featured"] is False
    assert body["capsule_count"] == 0


@pytest.mark.asyncio
async def test_create_leader_duplicate_slug(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create first
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Leader One",
                "slug": "dup-slug",
                "description": "First",
            },
            cookies=admin_cookies,
        )
        # Create duplicate
        resp = await ac.post(
            "/api/leaders/",
            json={
                "name": "Leader Two",
                "slug": "dup-slug",
                "description": "Second",
            },
            cookies=admin_cookies,
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_leaders_public(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a leader first
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Public Leader",
                "slug": "public-leader",
                "description": "Publicly visible",
            },
            cookies=admin_cookies,
        )
        # List without auth
        resp = await ac.get("/api/leaders/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    slugs = [l["slug"] for l in body["leaders"]]
    assert "public-leader" in slugs


@pytest.mark.asyncio
async def test_get_leader_by_slug(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Slug Leader",
                "slug": "slug-leader",
                "description": "Get by slug test",
            },
            cookies=admin_cookies,
        )
        resp = await ac.get("/api/leaders/slug-leader")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "slug-leader"


@pytest.mark.asyncio
async def test_get_leader_not_found(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/leaders/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_leader(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Update Me",
                "slug": "update-me",
                "description": "Original",
            },
            cookies=admin_cookies,
        )
        resp = await ac.put(
            "/api/leaders/update-me",
            json={"bio": "Updated bio", "is_featured": True},
            cookies=admin_cookies,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bio"] == "Updated bio"
    assert body["is_featured"] is True
    assert body["name"] == "Update Me"  # unchanged


@pytest.mark.asyncio
async def test_delete_leader(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Delete Me",
                "slug": "delete-me",
                "description": "To be deleted",
            },
            cookies=admin_cookies,
        )
        resp = await ac.delete("/api/leaders/delete-me", cookies=admin_cookies)
    assert resp.status_code == 204

    # Verify it's gone
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/leaders/delete-me")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_leaders_search_filter(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Searchable Leader",
                "slug": "searchable",
                "description": "Unique description for searching",
                "expertise_domain": "AI",
            },
            cookies=admin_cookies,
        )
        # Search by name
        resp = await ac.get("/api/leaders/?search=Searchable")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_list_leaders_domain_filter(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Domain Leader",
                "slug": "domain-leader",
                "description": "Domain filter test",
                "expertise_domain": "Robotics",
            },
            cookies=admin_cookies,
        )
        resp = await ac.get("/api/leaders/?domain=Robotics")
    assert resp.status_code == 200
    body = resp.json()
    assert all(l["expertise_domain"] == "Robotics" for l in body["leaders"])


# ---------------------------------------------------------------------------
# Task 5 & 6: CaptureRequest leader_id + leader capsules endpoint
# ---------------------------------------------------------------------------


def test_capture_request_accepts_leader_id():
    """CaptureRequest schema accepts optional leader_id field."""
    req = CaptureRequest(content="some content", leader_id="abc-123")
    assert req.leader_id == "abc-123"


def test_capture_request_leader_id_defaults_none():
    """CaptureRequest.leader_id defaults to None for backward compatibility."""
    req = CaptureRequest(content="some content")
    assert req.leader_id is None


@pytest.mark.asyncio
async def test_get_leader_capsules_empty(app, admin_cookies):
    """GET /api/leaders/{slug}/capsules returns empty list for leader with no capsules."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a leader
        await ac.post(
            "/api/leaders/",
            json={
                "name": "Empty Leader",
                "slug": "empty-leader",
                "description": "Leader with no capsules",
            },
            cookies=admin_cookies,
        )
        # Get capsules (public, no auth needed)
        resp = await ac.get("/api/leaders/empty-leader/capsules")
    assert resp.status_code == 200
    body = resp.json()
    assert body["capsules"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_get_leader_capsules_not_found(app):
    """GET /api/leaders/nonexistent/capsules returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/leaders/nonexistent/capsules")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Leader not found"
