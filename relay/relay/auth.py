"""API key generation, hashing, and validation."""

import logging
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from . import db as db_ops

logger = logging.getLogger(__name__)

_ph = PasswordHasher()

KEY_PREFIX_LEN = 19  # "sieve_live_" (11) + 8 hex chars

# Pre-computed dummy hash so prefix-miss takes the same time as prefix-hit.
# Generated from an impossible key value — never matches any real input.
_DUMMY_HASH = _ph.hash("sieve_dummy_never_matches_any_real_key")


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


class AuthError(Exception):
    """Raised on any authentication failure."""

    def __init__(self, message: str, *, rate_limited: bool = False):
        super().__init__(message)
        self.rate_limited = rate_limited


async def validate_key(db_conn, bearer_token: str) -> dict:
    """Validate a Bearer token and return the key record.

    Raises:
        AuthError: If key is invalid, inactive, or rate limited.
    """
    # Strip "Bearer " prefix if present
    raw_key = bearer_token.removeprefix("Bearer ").strip()

    if not raw_key.startswith("sieve_live_"):
        # Still do a dummy verify to keep timing constant
        verify_key("dummy", _DUMMY_HASH)
        raise AuthError("Invalid API key")

    prefix = get_key_prefix(raw_key)
    key_record = await db_ops.find_key_by_prefix(db_conn, prefix)

    if not key_record:
        # Constant-time: run argon2 verify even when prefix is unknown
        verify_key(raw_key, _DUMMY_HASH)
        raise AuthError("Invalid API key")

    if not verify_key(raw_key, key_record["key_hash"]):
        raise AuthError("Invalid API key")

    # Atomic rate-limit check: insert-and-count in one transaction
    allowed = await db_ops.check_and_log_rate_limit(
        db_conn, key_record["id"], key_record["rate_limit"]
    )
    if not allowed:
        raise AuthError("Rate limit exceeded", rate_limited=True)

    await db_ops.update_key_last_used(db_conn, key_record["id"])

    return key_record
