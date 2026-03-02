import pytest


@pytest.mark.asyncio
async def test_full_social_flow(client, db_session):
    """End-to-end: signup, capture, make public, follow, see in feed."""
    # User 1 signs up
    resp = await client.post("/api/auth/signup", json={
        "email": "alice@test.com", "password": "pass123",
        "display_name": "Alice", "username": "alice",
    })
    assert resp.status_code == 201
    token1 = resp.json()["access_token"]
    cookies1 = {"sieve_token": token1}

    # User 1 captures a note
    resp = await client.post("/api/capsules/", cookies=cookies1, json={
        "title": "Alice's Insight",
        "executive_summary": "Great insight",
        "core_insight": "The key takeaway",
        "full_content": "Full content here",
        "tags": ["ai"],
    })
    assert resp.status_code == 201

    # User 1 makes sieve public
    resp = await client.put("/api/sieves/me", cookies=cookies1, json={"is_public": True})
    assert resp.status_code == 200

    # User 2 signs up
    resp = await client.post("/api/auth/signup", json={
        "email": "bob@test.com", "password": "pass123",
        "display_name": "Bob", "username": "bob",
    })
    token2 = resp.json()["access_token"]
    cookies2 = {"sieve_token": token2}

    # User 2 discovers Alice
    resp = await client.get("/api/discover/sieves")
    data = resp.json()
    assert any(s["username"] == "alice" for s in data["sieves"])

    # User 2 follows Alice
    resp = await client.post("/api/sieves/@alice/follow", cookies=cookies2)
    assert resp.status_code == 201

    # User 2 sees Alice's capsule in feed
    resp = await client.get("/api/feed/", cookies=cookies2)
    data = resp.json()
    assert any(c["title"] == "Alice's Insight" for c in data["capsules"])

    # User 2 unfollows Alice
    resp = await client.delete("/api/sieves/@alice/follow", cookies=cookies2)
    assert resp.status_code == 204

    # User 2 no longer sees Alice's capsule in feed
    resp = await client.get("/api/feed/", cookies=cookies2)
    data = resp.json()
    assert not any(c["title"] == "Alice's Insight" for c in data["capsules"])
