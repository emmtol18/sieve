import pytest
from sieve.api.auth.deps import create_access_token, hash_password
from sieve.db.models import Capsule, Follow, Sieve, User


pytestmark = pytest.mark.anyio


async def _create_other_user(
    db_session, email="other@example.com", username="otheruser", public=True
) -> tuple[User, Sieve]:
    """Helper to create another user+sieve for feed tests."""
    user = User(
        email=email,
        password_hash=hash_password("password2"),
        display_name="Other User",
        username=username,
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Other Sieve", is_public=public)
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(sieve)
    return user, sieve


def _make_capsule(sieve_id, title="Test Capsule", status="active") -> Capsule:
    return Capsule(
        sieve_id=sieve_id,
        title=title,
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        status=status,
    )


async def test_feed_shows_own_capsules(client, db_session, test_user, auth_cookies):
    """Capsules in the user's own sieve appear in the feed."""
    _, sieve = test_user

    capsule = _make_capsule(sieve.id, title="My Own Capsule")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/feed/", cookies=auth_cookies)
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert len(data["capsules"]) == 1
    assert data["capsules"][0]["title"] == "My Own Capsule"


async def test_feed_shows_followed_capsules(client, db_session, test_user, auth_cookies):
    """Capsules from followed sieves appear in the feed."""
    _, my_sieve = test_user

    # Create a second user and follow them
    user2, sieve2 = await _create_other_user(db_session, public=True)
    follow = Follow(follower_sieve_id=my_sieve.id, followed_sieve_id=sieve2.id)
    db_session.add(follow)

    # Create a capsule in the followed sieve
    capsule = _make_capsule(sieve2.id, title="Followed Capsule")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/feed/", cookies=auth_cookies)
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    titles = [c["title"] for c in data["capsules"]]
    assert "Followed Capsule" in titles


async def test_feed_excludes_unfollowed(client, db_session, test_user, auth_cookies):
    """Capsules from sieves the user does NOT follow are excluded."""
    _, my_sieve = test_user

    # Create a stranger (not followed)
    _, stranger_sieve = await _create_other_user(
        db_session, email="stranger@example.com", username="stranger", public=True
    )

    # Create a capsule in the stranger's sieve
    capsule = _make_capsule(stranger_sieve.id, title="Stranger Capsule")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/feed/", cookies=auth_cookies)
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 0
    assert len(data["capsules"]) == 0


async def test_feed_excludes_inactive_capsules(client, db_session, test_user, auth_cookies):
    """Archived/inactive capsules from own sieve are excluded from feed."""
    _, sieve = test_user

    capsule = _make_capsule(sieve.id, title="Archived", status="archived")
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/feed/", cookies=auth_cookies)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_feed_pagination(client, db_session, test_user, auth_cookies):
    """Feed respects limit and offset parameters."""
    _, sieve = test_user

    for i in range(5):
        db_session.add(_make_capsule(sieve.id, title=f"Capsule {i}"))
    await db_session.commit()

    resp = await client.get("/api/feed/?limit=2&offset=0", cookies=auth_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert len(data["capsules"]) == 2

    resp2 = await client.get("/api/feed/?limit=2&offset=4", cookies=auth_cookies)
    data2 = resp2.json()
    assert data2["total"] == 5
    assert len(data2["capsules"]) == 1


async def test_feed_requires_auth(client):
    """Feed endpoint returns 401 without authentication."""
    resp = await client.get("/api/feed/")
    assert resp.status_code == 401
