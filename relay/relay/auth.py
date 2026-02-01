"""API key generation, hashing, and validation."""

import logging
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from . import db as db_ops

logger = logging.getLogger(__name__)

_ph = PasswordHasher()

KEY_PREFIX_LEN = 19  # "sieve_live_" (11) + 8 hex chars


def generate_raw_key() -> str:
    """Generate a new API key string."""
    hex_part = secrets.token_hex(16)  # 32 hex chars
    return f"sieve_live_{hex_part}"


def hash_key(raw_key: str) -> str:
    """Hash an API key with argon2id."""
    return _ph.hash(raw_key)


def verify_key(raw_key: str, key_hash: str) -> bool:
    """Verify a raw key against its argon2id hash."""
    try:
        return _ph.verify(key_hash, raw_key)
    except VerifyMismatchError:
        return False


def get_key_prefix(raw_key: str) -> str:
    """Extract the lookup prefix from a raw key."""
    return raw_key[:KEY_PREFIX_LEN]


async def generate_key(
    db_conn,
    name: str,
    is_admin: bool = False,
    rate_limit: int = 60,
) -> str:
    """Generate a new API key, store its hash, and return the raw key (shown once)."""
    raw_key = generate_raw_key()
    key_hash = hash_key(raw_key)
    prefix = get_key_prefix(raw_key)

    await db_ops.store_api_key(
        db_conn,
        name=name,
        key_hash=key_hash,
        key_prefix=prefix,
        is_admin=is_admin,
        rate_limit=rate_limit,
    )

    logger.info(f"[AUTH] Created key '{name}' (prefix: {prefix}, admin: {is_admin})")
    return raw_key


async def validate_key(db_conn, bearer_token: str) -> dict:
    """Validate a Bearer token and return the key record.

    Raises:
        ValueError: If key is invalid, inactive, or rate limited.
    """
    # Strip "Bearer " prefix if present
    raw_key = bearer_token.removeprefix("Bearer ").strip()

    if not raw_key.startswith("sieve_live_"):
        raise ValueError("Invalid API key format")

    prefix = get_key_prefix(raw_key)
    key_record = await db_ops.find_key_by_prefix(db_conn, prefix)

    if not key_record:
        raise ValueError("Invalid API key")

    if not verify_key(raw_key, key_record["key_hash"]):
        raise ValueError("Invalid API key")

    # Check rate limit
    allowed = await db_ops.check_rate_limit(
        db_conn, key_record["id"], key_record["rate_limit"]
    )
    if not allowed:
        raise ValueError("Rate limit exceeded")

    # Log the request and update last_used
    await db_ops.log_rate_limit(db_conn, key_record["id"])
    await db_ops.update_key_last_used(db_conn, key_record["id"])

    return key_record
