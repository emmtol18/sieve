import uuid as _uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import String, Text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sieve.api.auth.deps import create_access_token, hash_password
from sieve.config import Settings
from sieve.db.models import Base, Sieve, User


@pytest.fixture
def settings():
    return Settings(database_url="sqlite+aiosqlite:///test.db")


def _patch_pg_types_for_sqlite():
    """Patch PostgreSQL UUID and ARRAY types to work with SQLite.

    - UUID: compiles to CHAR(32) and accepts both uuid.UUID and str bind values.
    - ARRAY: compiles to TEXT (values stored as-is by SQLAlchemy).
    """
    from sqlalchemy.dialects.postgresql import ARRAY, UUID
    from sqlalchemy.ext.compiler import compiles

    @compiles(UUID, "sqlite")
    def compile_uuid_sqlite(type_, compiler, **kw):
        return "CHAR(32)"

    @compiles(ARRAY, "sqlite")
    def compile_array_sqlite(type_, compiler, **kw):
        return "TEXT"

    # Override ARRAY bind/result processors so SQLite can store Python lists
    # as comma-separated strings and reconstruct them on read.
    import json as _json

    _orig_array_bind = ARRAY.bind_processor

    def _array_bind_processor(self, dialect):
        if dialect.name == "sqlite":

            def process(value):
                if value is None:
                    return None
                if isinstance(value, list):
                    return _json.dumps(value)
                return value

            return process
        return _orig_array_bind(self, dialect)

    ARRAY.bind_processor = _array_bind_processor

    _orig_array_result = ARRAY.result_processor

    def _array_result_processor(self, dialect, coltype=None):
        if dialect.name == "sqlite":

            def process(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    try:
                        return _json.loads(value)
                    except _json.JSONDecodeError:
                        return value.split(",") if value else []
                if isinstance(value, list):
                    return value
                return value

            return process
        return _orig_array_result(self, dialect, coltype)

    ARRAY.result_processor = _array_result_processor

    # Override UUID bind/result processors so SQLite can handle both
    # uuid.UUID objects and plain strings (e.g. from JWT tokens).
    _orig_bind_processor = UUID.bind_processor

    def _uuid_bind_processor(self, dialect):
        if dialect.name == "sqlite":

            def process(value):
                if value is not None:
                    if isinstance(value, _uuid.UUID):
                        return value.hex
                    # Already a string — strip dashes for CHAR(32) storage
                    return str(value).replace("-", "")
                return value

            return process
        return _orig_bind_processor(self, dialect)

    UUID.bind_processor = _uuid_bind_processor

    _orig_result_processor = UUID.result_processor

    def _uuid_result_processor(self, dialect, coltype=None):
        if dialect.name == "sqlite":

            def process(value):
                if value is not None:
                    if isinstance(value, _uuid.UUID):
                        return value
                    return _uuid.UUID(str(value))
                return value

            return process
        return _orig_result_processor(self, dialect, coltype)

    UUID.result_processor = _uuid_result_processor


# Apply patches once at import time so they're active for all tests.
_patch_pg_types_for_sqlite()


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    # Enable foreign keys in SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def app(db_engine):
    from sieve.api.app import create_app
    from sieve.db.database import get_db

    test_app = create_app()

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(db_session):
    """Create a test user with a sieve and return (user, sieve)."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword"),
        display_name="Test User",
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Test Sieve")
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(sieve)
    return user, sieve


@pytest.fixture
def auth_cookies(test_user):
    """Return cookies dict with valid sieve_token for the test user."""
    user, _ = test_user
    token = create_access_token(str(user.id))
    return {"sieve_token": token}
