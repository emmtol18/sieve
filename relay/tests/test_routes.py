"""Tests for relay API routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from relay.app import create_app
from relay.auth import generate_key
from relay.config import RelaySettings
from relay.db import get_db, init_db


@pytest.fixture
def relay_settings(tmp_path):
    return RelaySettings(db_path=tmp_path / "test.db")


@pytest.fixture
def app(relay_settings):
    return create_app(relay_settings)


@pytest.fixture
async def client(app, relay_settings):
    """Create a test client with initialized DB and keys."""
    await init_db(relay_settings.db_path)
    app.state.db = await get_db(relay_settings.db_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await app.state.db.close()


@pytest.fixture
async def keys(app):
    """Generate test API keys. Returns (regular_key, admin_key)."""
    db = app.state.db
    regular = await generate_key(db, name="regular", is_admin=False, rate_limit=60)
    admin = await generate_key(db, name="admin", is_admin=True, rate_limit=60)
    return regular, admin


def _auth(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


class TestHealthEndpoint:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_security_headers(self, client):
        resp = await client.get("/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "no-referrer"
        assert resp.headers["Cache-Control"] == "no-store"


class TestCaptureEndpoint:
    async def test_capture_url(self, client, keys):
        regular, _ = keys
        resp = await client.post(
            "/capture",
            json={"url": "https://example.com"},
            headers=_auth(regular),
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "pending"
        assert "id" in data

    async def test_capture_content(self, client, keys):
        regular, _ = keys
        resp = await client.post(
            "/capture",
            json={"content": "Some interesting article text"},
            headers=_auth(regular),
        )
        assert resp.status_code == 202

    async def test_capture_with_all_fields(self, client, keys):
        regular, _ = keys
        resp = await client.post(
            "/capture",
            json={
                "content": "Article text",
                "url": "https://example.com",
                "source_url": "https://example.com/original",
                "title": "Test Article",
            },
            headers=_auth(regular),
        )
        assert resp.status_code == 202

    async def test_capture_missing_content_and_url(self, client, keys):
        regular, _ = keys
        resp = await client.post(
            "/capture",
            json={},
            headers=_auth(regular),
        )
        assert resp.status_code == 422

    async def test_capture_invalid_url(self, client, keys):
        regular, _ = keys
        resp = await client.post(
            "/capture",
            json={"url": "ftp://example.com"},
            headers=_auth(regular),
        )
        assert resp.status_code == 422

    async def test_capture_no_auth(self, client):
        resp = await client.post(
            "/capture",
            json={"url": "https://example.com"},
        )
        assert resp.status_code == 401
        # Should not leak details about why auth failed
        assert resp.json()["detail"] == "Unauthorized"

    async def test_capture_bad_auth(self, client):
        resp = await client.post(
            "/capture",
            json={"url": "https://example.com"},
            headers={"Authorization": "Bearer invalid_key"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Unauthorized"

    async def test_capture_rate_limited(self, client, app):
        """Key with rate_limit=2 should be blocked after 2 calls."""
        db = app.state.db
        limited_key = await generate_key(db, name="limited", rate_limit=2)

        for _ in range(2):
            resp = await client.post(
                "/capture",
                json={"url": "https://example.com"},
                headers=_auth(limited_key),
            )
            assert resp.status_code == 202

        resp = await client.post(
            "/capture",
            json={"url": "https://example.com"},
            headers=_auth(limited_key),
        )
        assert resp.status_code == 429


class TestPendingEndpoint:
    async def test_get_pending_admin(self, client, keys):
        regular, admin = keys

        # Create some captures
        await client.post(
            "/capture", json={"url": "https://a.com"}, headers=_auth(regular)
        )
        await client.post(
            "/capture", json={"url": "https://b.com"}, headers=_auth(regular)
        )

        # Fetch pending with admin key
        resp = await client.get("/captures/pending", headers=_auth(admin))
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["captures"]) == 2

    async def test_get_pending_non_admin(self, client, keys):
        regular, _ = keys
        resp = await client.get("/captures/pending", headers=_auth(regular))
        assert resp.status_code == 403

    async def test_get_pending_no_auth(self, client):
        resp = await client.get("/captures/pending")
        assert resp.status_code == 401

    async def test_get_pending_negative_limit(self, client, keys):
        _, admin = keys
        resp = await client.get(
            "/captures/pending?limit=-1", headers=_auth(admin)
        )
        assert resp.status_code == 422

    async def test_get_pending_zero_limit(self, client, keys):
        _, admin = keys
        resp = await client.get(
            "/captures/pending?limit=0", headers=_auth(admin)
        )
        assert resp.status_code == 422


class TestAckEndpoint:
    async def test_ack_capture(self, client, keys):
        regular, admin = keys

        # Create a capture
        resp = await client.post(
            "/capture", json={"url": "https://example.com"}, headers=_auth(regular)
        )
        capture_id = resp.json()["id"]

        # Ack it
        resp = await client.post(
            f"/captures/{capture_id}/ack", headers=_auth(admin)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "acked"

        # Verify it's no longer pending
        resp = await client.get("/captures/pending", headers=_auth(admin))
        assert resp.json()["count"] == 0

    async def test_ack_nonexistent(self, client, keys):
        _, admin = keys
        resp = await client.post("/captures/99999/ack", headers=_auth(admin))
        assert resp.status_code == 404

    async def test_ack_non_admin(self, client, keys):
        regular, _ = keys
        resp = await client.post("/captures/1/ack", headers=_auth(regular))
        assert resp.status_code == 403

    async def test_ack_no_auth(self, client):
        resp = await client.post("/captures/1/ack")
        assert resp.status_code == 401
