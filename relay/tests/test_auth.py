"""Tests for API key generation, validation, and rate limiting."""

import pytest

from relay.auth import (
    generate_key,
    generate_raw_key,
    get_key_prefix,
    hash_key,
    validate_key,
    verify_key,
)
from relay.db import store_api_key


class TestKeyGeneration:
    def test_raw_key_format(self):
        key = generate_raw_key()
        assert key.startswith("sieve_live_")
        # "sieve_live_" (11) + 32 hex chars = 43
        assert len(key) == 43

    def test_raw_key_uniqueness(self):
        keys = {generate_raw_key() for _ in range(100)}
        assert len(keys) == 100

    def test_prefix_extraction(self):
        key = "sieve_live_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        prefix = get_key_prefix(key)
        assert prefix == "sieve_live_a1b2c3d4"
        assert len(prefix) == 19

    def test_hash_and_verify(self):
        key = generate_raw_key()
        hashed = hash_key(key)
        assert verify_key(key, hashed)

    def test_verify_wrong_key(self):
        key = generate_raw_key()
        hashed = hash_key(key)
        wrong_key = generate_raw_key()
        assert not verify_key(wrong_key, hashed)


class TestKeyStorage:
    async def test_generate_and_validate(self, db):
        raw_key = await generate_key(db, name="test", is_admin=False)
        record = await validate_key(db, raw_key)
        assert record["name"] == "test"
        assert record["is_admin"] == 0

    async def test_generate_admin_key(self, db):
        raw_key = await generate_key(db, name="admin", is_admin=True)
        record = await validate_key(db, raw_key)
        assert record["is_admin"] == 1

    async def test_validate_with_bearer_prefix(self, db):
        raw_key = await generate_key(db, name="test")
        record = await validate_key(db, f"Bearer {raw_key}")
        assert record["name"] == "test"


class TestKeyValidation:
    async def test_invalid_format(self, db):
        with pytest.raises(ValueError, match="Invalid API key format"):
            await validate_key(db, "not_a_valid_key")

    async def test_unknown_prefix(self, db):
        with pytest.raises(ValueError, match="Invalid API key"):
            await validate_key(db, "sieve_live_00000000000000000000000000000000")

    async def test_wrong_key_body(self, db):
        """Key with valid prefix but wrong body after prefix."""
        raw_key = await generate_key(db, name="test")
        # Replace the last char to make it invalid
        bad_key = raw_key[:-1] + ("0" if raw_key[-1] != "0" else "1")
        with pytest.raises(ValueError, match="Invalid API key"):
            await validate_key(db, bad_key)


class TestRateLimiting:
    async def test_rate_limit_enforced(self, db):
        raw_key = await generate_key(db, name="limited", rate_limit=3)

        # First 3 calls should succeed
        for _ in range(3):
            await validate_key(db, raw_key)

        # 4th should fail
        with pytest.raises(ValueError, match="Rate limit"):
            await validate_key(db, raw_key)

    async def test_different_keys_independent_limits(self, db):
        key1 = await generate_key(db, name="key1", rate_limit=2)
        key2 = await generate_key(db, name="key2", rate_limit=2)

        # Exhaust key1's limit
        await validate_key(db, key1)
        await validate_key(db, key1)

        # key2 should still work
        record = await validate_key(db, key2)
        assert record["name"] == "key2"
