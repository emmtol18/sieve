"""Shared fixtures for relay tests."""

from pathlib import Path

import pytest
import pytest_asyncio

from relay.auth import generate_key
from relay.config import RelaySettings
from relay.db import get_db, init_db


@pytest.fixture
def relay_settings(tmp_path: Path) -> RelaySettings:
    """Create settings with a temporary database."""
    return RelaySettings(db_path=tmp_path / "test_relay.db")


@pytest_asyncio.fixture
async def db(relay_settings: RelaySettings):
    """Initialize database and return connection."""
    await init_db(relay_settings.db_path)
    conn = await get_db(relay_settings.db_path)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def api_key(db) -> str:
    """Generate a standard API key and return the raw key."""
    return await generate_key(db, name="test-key", is_admin=False, rate_limit=60)


@pytest_asyncio.fixture
async def admin_key(db) -> str:
    """Generate an admin API key and return the raw key."""
    return await generate_key(db, name="test-admin", is_admin=True, rate_limit=60)
