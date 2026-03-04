"""Tests for signup username support across all signup paths."""


async def test_signup_requires_username(client):
    """Signup creates user with username."""
    resp = await client.post("/api/auth/signup", json={
        "email": "new@test.com",
        "password": "secret123",
        "display_name": "New User",
        "username": "newuser",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data


async def test_signup_duplicate_username_rejected(client, test_user):
    """Duplicate username returns 409."""
    resp = await client.post("/api/auth/signup", json={
        "email": "another@test.com",
        "password": "secret123",
        "display_name": "Another",
        "username": "testuser",  # same as test_user
    })
    assert resp.status_code == 409


async def test_signup_missing_username_rejected(client):
    """Signup without username returns 422 (validation error)."""
    resp = await client.post("/api/auth/signup", json={
        "email": "nouser@test.com",
        "password": "secret123",
        "display_name": "No User",
    })
    assert resp.status_code == 422


async def test_signup_invalid_username_rejected(client):
    """Signup with invalid username format returns 422."""
    resp = await client.post("/api/auth/signup", json={
        "email": "bad@test.com",
        "password": "secret123",
        "display_name": "Bad User",
        "username": "AB",  # too short and uppercase
    })
    assert resp.status_code == 422


async def test_signup_username_with_spaces_rejected(client):
    """Signup with spaces in username returns 422."""
    resp = await client.post("/api/auth/signup", json={
        "email": "spaces@test.com",
        "password": "secret123",
        "display_name": "Space User",
        "username": "has spaces",
    })
    assert resp.status_code == 422


async def test_signup_duplicate_email_still_rejected(client, test_user):
    """Duplicate email still returns 409."""
    resp = await client.post("/api/auth/signup", json={
        "email": "test@example.com",  # same as test_user
        "password": "secret123",
        "display_name": "Another",
        "username": "differentuser",
    })
    assert resp.status_code == 409


async def test_htmx_signup_requires_username(client):
    """HTMX signup creates user with username."""
    resp = await client.post("/htmx/auth/signup", data={
        "email": "htmx@test.com",
        "password": "secret123",
        "display_name": "HTMX User",
        "username": "htmxuser",
    })
    assert resp.status_code == 200
    assert "Account created" in resp.text


async def test_htmx_signup_missing_username(client):
    """HTMX signup without username returns error message."""
    resp = await client.post("/htmx/auth/signup", data={
        "email": "htmx2@test.com",
        "password": "secret123",
        "display_name": "HTMX User 2",
    })
    assert resp.status_code == 200
    assert "All fields are required" in resp.text


async def test_htmx_signup_duplicate_username(client, test_user):
    """HTMX signup with duplicate username returns error message."""
    resp = await client.post("/htmx/auth/signup", data={
        "email": "htmx3@test.com",
        "password": "secret123",
        "display_name": "HTMX User 3",
        "username": "testuser",  # same as test_user
    })
    assert resp.status_code == 200
    assert "Username already taken" in resp.text


async def test_htmx_signup_invalid_username(client):
    """HTMX signup with invalid username returns error message."""
    resp = await client.post("/htmx/auth/signup", data={
        "email": "htmx4@test.com",
        "password": "secret123",
        "display_name": "HTMX User 4",
        "username": "AB",  # too short
    })
    assert resp.status_code == 200
    assert "3-50 characters" in resp.text
