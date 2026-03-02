import pytest
from sieve.api.auth.deps import hash_password
from sieve.db.models import Capsule, Sieve, User


pytestmark = pytest.mark.anyio


async def _create_user_with_sieve(
    db_session,
    email: str,
    username: str,
    display_name: str = "User",
    public: bool = True,
) -> tuple[User, Sieve]:
    """Helper to create a user+sieve for discover tests."""
    user = User(
        email=email,
        password_hash=hash_password("password"),
        display_name=display_name,
        username=username,
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name=f"{username}'s Sieve", is_public=public)
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(sieve)
    return user, sieve


def _make_capsule(sieve_id, title="Test Capsule", tags=None, category=None, status="active"):
    return Capsule(
        sieve_id=sieve_id,
        title=title,
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        tags=tags or [],
        category=category or "",
        status=status,
    )


# ---- Discover Sieves ----


async def test_discover_returns_public_sieves(client, db_session):
    """Public sieves appear in discover; private sieves do not."""
    await _create_user_with_sieve(
        db_session, "pub@example.com", "publicuser", "Public User", public=True
    )
    await _create_user_with_sieve(
        db_session, "priv@example.com", "privateuser", "Private User", public=False
    )

    resp = await client.get("/api/discover/sieves")
    assert resp.status_code == 200

    data = resp.json()
    usernames = [s["username"] for s in data["sieves"]]
    assert "publicuser" in usernames
    assert "privateuser" not in usernames
    assert data["total"] == 1


async def test_discover_sieves_search(client, db_session):
    """Search filters sieves by name or display_name."""
    await _create_user_with_sieve(
        db_session, "a@example.com", "alice", "Alice Smith", public=True
    )
    await _create_user_with_sieve(
        db_session, "b@example.com", "bob", "Bob Jones", public=True
    )

    resp = await client.get("/api/discover/sieves?search=alice")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["sieves"][0]["username"] == "alice"


async def test_discover_sieves_no_auth_required(client, db_session):
    """Discover sieves endpoint does not require authentication."""
    resp = await client.get("/api/discover/sieves")
    assert resp.status_code == 200


# ---- Discover Capsules ----


async def test_discover_capsules_from_public_sieves(client, db_session):
    """Active capsules from public sieves appear in discover."""
    _, sieve = await _create_user_with_sieve(
        db_session, "pub@example.com", "publicuser", public=True
    )

    capsule = _make_capsule(sieve.id, title="Public Capsule")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/discover/capsules")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["capsules"][0]["title"] == "Public Capsule"


async def test_discover_excludes_private_sieve_capsules(client, db_session):
    """Capsules from private sieves are hidden from discover."""
    _, private_sieve = await _create_user_with_sieve(
        db_session, "priv@example.com", "privateuser", public=False
    )

    capsule = _make_capsule(private_sieve.id, title="Secret Capsule")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/discover/capsules")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 0
    assert len(data["capsules"]) == 0


async def test_discover_search_by_tag(client, db_session):
    """Capsules can be filtered by tag."""
    _, sieve = await _create_user_with_sieve(
        db_session, "pub@example.com", "publicuser", public=True
    )

    capsule_with_tag = _make_capsule(sieve.id, title="Tagged", tags=["python", "async"])
    capsule_no_tag = _make_capsule(sieve.id, title="No Tag", tags=["javascript"])
    db_session.add(capsule_with_tag)
    db_session.add(capsule_no_tag)
    await db_session.commit()

    resp = await client.get("/api/discover/capsules?tag=python")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["capsules"][0]["title"] == "Tagged"


async def test_discover_search_by_category(client, db_session):
    """Capsules can be filtered by category."""
    _, sieve = await _create_user_with_sieve(
        db_session, "pub@example.com", "publicuser", public=True
    )

    capsule = _make_capsule(sieve.id, title="Tech Capsule", category="Technology")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/discover/capsules?category=Technology")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["capsules"][0]["title"] == "Tech Capsule"


async def test_discover_capsules_search_text(client, db_session):
    """Capsules can be searched by title text."""
    _, sieve = await _create_user_with_sieve(
        db_session, "pub@example.com", "publicuser", public=True
    )

    capsule = _make_capsule(sieve.id, title="Understanding Async Python")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/discover/capsules?search=Async")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["capsules"][0]["title"] == "Understanding Async Python"


async def test_discover_excludes_inactive_capsules(client, db_session):
    """Archived capsules are excluded from discover even from public sieves."""
    _, sieve = await _create_user_with_sieve(
        db_session, "pub@example.com", "publicuser", public=True
    )

    capsule = _make_capsule(sieve.id, title="Archived", status="archived")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/discover/capsules")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
