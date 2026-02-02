"""Tests for database CRUD operations."""

import pytest

from relay.db import (
    ack_capture,
    count_pending,
    create_capture,
    get_pending,
    list_api_keys,
    revoke_key,
    store_api_key,
)


class TestCapturesCRUD:
    async def test_create_capture(self, db):
        key_id = await store_api_key(db, "test", "hash", "prefix", is_admin=False)
        result = await create_capture(
            db,
            api_key_id=key_id,
            content="test content",
            url=None,
            source_url=None,
            title="Test",
            image_data=None,
        )
        assert result["id"] is not None
        assert result["status"] == "pending"

    async def test_get_pending(self, db):
        key_id = await store_api_key(db, "test", "hash", "prefix", is_admin=False)

        # Create 3 captures
        for i in range(3):
            await create_capture(
                db, key_id, f"content {i}", None, None, f"Title {i}", None
            )

        pending = await get_pending(db)
        assert len(pending) == 3
        # Should be ordered by creation time
        assert pending[0]["content"] == "content 0"
        assert pending[2]["content"] == "content 2"

    async def test_get_pending_limit(self, db):
        key_id = await store_api_key(db, "test", "hash", "prefix", is_admin=False)
        for i in range(5):
            await create_capture(db, key_id, f"content {i}", None, None, None, None)

        pending = await get_pending(db, limit=2)
        assert len(pending) == 2

    async def test_ack_capture(self, db):
        key_id = await store_api_key(db, "test", "hash", "prefix", is_admin=False)
        result = await create_capture(db, key_id, "content", None, None, None, None)

        success = await ack_capture(db, result["id"])
        assert success is True

        # Should no longer be pending
        pending = await get_pending(db)
        assert len(pending) == 0

    async def test_ack_nonexistent(self, db):
        success = await ack_capture(db, 99999)
        assert success is False

    async def test_ack_already_acked(self, db):
        key_id = await store_api_key(db, "test", "hash", "prefix", is_admin=False)
        result = await create_capture(db, key_id, "content", None, None, None, None)

        await ack_capture(db, result["id"])
        # Second ack should return False
        success = await ack_capture(db, result["id"])
        assert success is False

    async def test_count_pending(self, db):
        key_id = await store_api_key(db, "test", "hash", "prefix", is_admin=False)

        assert await count_pending(db) == 0

        for _ in range(3):
            await create_capture(db, key_id, "content", None, None, None, None)

        assert await count_pending(db) == 3

        # Ack one
        pending = await get_pending(db, limit=1)
        await ack_capture(db, pending[0]["id"])

        assert await count_pending(db) == 2


class TestApiKeysCRUD:
    async def test_store_and_list(self, db):
        await store_api_key(db, "key1", "hash1", "prefix1", is_admin=False)
        await store_api_key(db, "key2", "hash2", "prefix2", is_admin=True)

        keys = await list_api_keys(db)
        assert len(keys) == 2
        # Most recent first
        assert keys[0]["name"] == "key2"
        assert keys[1]["name"] == "key1"

    async def test_revoke_key(self, db):
        await store_api_key(db, "key1", "hash1", "prefix1", is_admin=False)

        success = await revoke_key(db, "prefix1")
        assert success is True

        keys = await list_api_keys(db)
        assert keys[0]["is_active"] == 0

    async def test_revoke_nonexistent(self, db):
        success = await revoke_key(db, "nonexistent")
        assert success is False

    async def test_capture_with_all_fields(self, db):
        key_id = await store_api_key(db, "test", "hash", "prefix", is_admin=False)
        result = await create_capture(
            db,
            api_key_id=key_id,
            content="article text",
            url="https://example.com",
            source_url="https://example.com/original",
            title="Test Article",
            image_data="base64data",
        )

        pending = await get_pending(db)
        assert len(pending) == 1
        cap = pending[0]
        assert cap["content"] == "article text"
        assert cap["url"] == "https://example.com"
        assert cap["source_url"] == "https://example.com/original"
        assert cap["title"] == "Test Article"
        assert cap["image_data"] == "base64data"
