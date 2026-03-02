import pytest
from sieve.api.auth.deps import create_access_token, hash_password
from sieve.db.models import Capsule, Follow, Sieve, User


pytestmark = pytest.mark.anyio


# ---- Task 4: Sieve Profile API ----


async def test_get_public_sieve_by_username(client, db_session, test_user):
    """GET /@username for a public sieve returns 200 with counts."""
    user, sieve = test_user
    sieve.is_public = True
    await db_session.commit()

    # Add a capsule to verify count
    capsule = Capsule(
        sieve_id=sieve.id,
        title="Test",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        status="active",
    )
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get(f"/api/sieves/@{user.username}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["username"] == "testuser"
    assert data["display_name"] == "Test User"
    assert data["is_public"] is True
    assert data["capsule_count"] == 1
    assert data["follower_count"] == 0
    assert data["following_count"] == 0


async def test_get_private_sieve_returns_404(client, db_session, test_user):
    """GET /@username for a private sieve returns 404."""
    user, sieve = test_user
    # sieve defaults to is_public=False
    assert sieve.is_public is False

    resp = await client.get(f"/api/sieves/@{user.username}")
    assert resp.status_code == 404


async def test_get_own_sieve_profile(client, db_session, test_user, auth_cookies):
    """GET /me with auth returns the user's own sieve profile."""
    user, sieve = test_user

    resp = await client.get("/api/sieves/me", cookies=auth_cookies)
    assert resp.status_code == 200

    data = resp.json()
    assert data["username"] == "testuser"
    assert data["name"] == "Test Sieve"
    assert data["capsule_count"] == 0
    assert data["follower_count"] == 0
    assert data["following_count"] == 0


async def test_update_sieve_profile(client, db_session, test_user, auth_cookies):
    """PUT /me with bio + is_public returns 200 with updated fields."""
    user, sieve = test_user

    resp = await client.put(
        "/api/sieves/me",
        json={"bio": "Hello world", "is_public": True},
        cookies=auth_cookies,
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["bio"] == "Hello world"
    assert data["is_public"] is True


# ---- Task 5: Follow/Unfollow API ----


async def _create_second_user(db_session, public: bool = True) -> tuple[User, Sieve]:
    """Helper to create a second user+sieve for follow tests."""
    user2 = User(
        email="other@example.com",
        password_hash=hash_password("password2"),
        display_name="Other User",
        username="otheruser",
    )
    db_session.add(user2)
    sieve2 = Sieve(user_id=user2.id, name="Other Sieve", is_public=public)
    db_session.add(sieve2)
    await db_session.commit()
    await db_session.refresh(user2)
    await db_session.refresh(sieve2)
    return user2, sieve2


async def test_follow_sieve(client, db_session, test_user, auth_cookies):
    """POST /@username/follow on a public sieve returns 201."""
    user2, sieve2 = await _create_second_user(db_session, public=True)

    resp = await client.post(
        f"/api/sieves/@{user2.username}/follow",
        cookies=auth_cookies,
    )
    assert resp.status_code == 201
    assert resp.json()["detail"] == "Followed"


async def test_unfollow_sieve(client, db_session, test_user, auth_cookies):
    """DELETE /@username/follow after following returns 204."""
    _, sieve = test_user
    user2, sieve2 = await _create_second_user(db_session, public=True)

    # Create a follow first
    follow = Follow(follower_sieve_id=sieve.id, followed_sieve_id=sieve2.id)
    db_session.add(follow)
    await db_session.commit()

    resp = await client.delete(
        f"/api/sieves/@{user2.username}/follow",
        cookies=auth_cookies,
    )
    assert resp.status_code == 204


async def test_cannot_follow_self(client, db_session, test_user, auth_cookies):
    """POST /@own_username/follow returns 400."""
    user, sieve = test_user
    sieve.is_public = True
    await db_session.commit()

    resp = await client.post(
        f"/api/sieves/@{user.username}/follow",
        cookies=auth_cookies,
    )
    assert resp.status_code == 400
    assert "Cannot follow yourself" in resp.json()["detail"]


async def test_follow_private_sieve_404(client, db_session, test_user, auth_cookies):
    """POST /@username/follow on a private sieve returns 404."""
    user2, sieve2 = await _create_second_user(db_session, public=False)

    resp = await client.post(
        f"/api/sieves/@{user2.username}/follow",
        cookies=auth_cookies,
    )
    assert resp.status_code == 404


async def test_follow_already_following_409(client, db_session, test_user, auth_cookies):
    """POST /@username/follow when already following returns 409."""
    _, sieve = test_user
    user2, sieve2 = await _create_second_user(db_session, public=True)

    # Create a follow first
    follow = Follow(follower_sieve_id=sieve.id, followed_sieve_id=sieve2.id)
    db_session.add(follow)
    await db_session.commit()

    resp = await client.post(
        f"/api/sieves/@{user2.username}/follow",
        cookies=auth_cookies,
    )
    assert resp.status_code == 409
    assert "Already following" in resp.json()["detail"]
