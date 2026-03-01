import pytest


@pytest.fixture
def settings():
    from sieve.config import Settings
    return Settings(database_url="sqlite+aiosqlite:///test.db")
