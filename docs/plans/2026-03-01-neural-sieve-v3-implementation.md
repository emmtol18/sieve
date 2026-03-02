# Neural Sieve v3 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a cloud-first, Obsidian-powered knowledge-to-skills pipeline that makes personal and curated thought-leader knowledge always available to Claude Code via MCP and compiled skills.

**Architecture:** Cloud backend (FastAPI + PostgreSQL) is the source of truth. MCP server connects to cloud API for always-on access. Skill compiler CLI transforms capsules into `.claude/skills/*.md`. Obsidian plugin (Phase 3) handles local capture processing and vault sync. Web dashboard (PWA) provides phone + desktop access.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async + asyncpg, PostgreSQL 16 + pgvector, OpenAI API, MCP SDK, HTMX + Jinja2, Click CLI, uv package manager.

**Reference codebases:**
- v1: `/Users/lucasfischer/Documents/Code/sieve_ideas/neural-sieve/` (MCP server, capsule schema, extraction pipeline)
- v2: `/Users/lucasfischer/Documents/Code/neural-sieve-v2/` (cloud backend, auth, capture pipeline, DB models)
- Obsidian repos: `/Users/lucasfischer/Documents/Code/neural-sieve-v3-research/`

---

## Phase 1: Core Pipeline (MVP)

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/sieve/__init__.py`
- Create: `src/sieve/cli.py`
- Create: `src/sieve/config.py`
- Create: `tests/conftest.py`
- Create: `.env.example`
- Create: `CLAUDE.md`
- Create: `Dockerfile`
- Create: `fly.toml`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "neural-sieve-v3"
version = "0.1.0"
description = "Cloud-first knowledge-to-skills pipeline"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "openai>=1.0",
    "mcp>=1.0",
    "httpx>=0.28",
    "jinja2>=3.1",
    "python-frontmatter>=1.1",
    "python-multipart>=0.0.18",
    "pyyaml>=6.0",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "passlib[bcrypt]>=1.7",
    "python-jose[cryptography]>=3.3",
    "pgvector>=0.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.9",
]

[project.scripts]
sieve = "sieve.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/sieve"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100
```

**Step 2: Create config.py**

Adapt from v2's `api/config.py`. Use pydantic-settings for env-based config.

```python
# src/sieve/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/neural_sieve_v3"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7

    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    search_model: str = "gpt-4o-mini"

    # Server
    host: str = "0.0.0.0"
    port: int = 8421

    # MCP
    sieve_api_url: str = "http://localhost:8421"
    sieve_api_key: str = ""

    model_config = {"env_prefix": "SIEVE_", "env_file": ".env"}


settings = Settings()
```

**Step 3: Create minimal CLI entry point**

```python
# src/sieve/cli.py
import click


@click.group()
def cli():
    """Neural Sieve v3 — Knowledge-to-Skills Pipeline"""
    pass


@cli.command()
def version():
    """Show version."""
    click.echo("neural-sieve-v3 0.1.0")
```

**Step 4: Create .env.example**

```
SIEVE_DATABASE_URL=postgresql+asyncpg://localhost:5432/neural_sieve_v3
SIEVE_JWT_SECRET=change-me-in-production
SIEVE_OPENAI_API_KEY=sk-...
```

**Step 5: Create CLAUDE.md**

```markdown
# Neural Sieve v3

## Dev Commands
- `uv run sieve version` — verify install
- `uv run pytest` — run tests
- `uv run sieve serve` — start API server
- `uv run sieve mcp` — start MCP server
- `uv run sieve compile` — compile skills

## Conventions
- Python 3.12+, async/await throughout
- SQLAlchemy async ORM, Alembic migrations
- Pydantic v2 for all schemas
- uv as package manager (mandatory)
- Tests with pytest-asyncio
```

**Step 6: Create __init__.py and conftest.py stubs**

```python
# src/sieve/__init__.py
```

```python
# tests/conftest.py
import pytest


@pytest.fixture
def settings():
    from sieve.config import Settings
    return Settings(database_url="sqlite+aiosqlite:///test.db")
```

**Step 7: Run to verify**

Run: `cd /Users/lucasfischer/Documents/Code/neural-sieve-v3 && uv sync && uv run sieve version`
Expected: `neural-sieve-v3 0.1.0`

**Step 8: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with CLI, config, and test infrastructure"
```

---

### Task 2: Database Models + Migrations

**Files:**
- Create: `src/sieve/db/__init__.py`
- Create: `src/sieve/db/database.py`
- Create: `src/sieve/db/models.py`
- Create: `alembic.ini`
- Create: `src/sieve/db/migrations/env.py`
- Create: `src/sieve/db/migrations/versions/001_initial_schema.py`
- Test: `tests/test_db_models.py`

**Step 1: Write failing test for database models**

```python
# tests/test_db_models.py
import uuid
from datetime import datetime, date

from sieve.db.models import User, Sieve, Capsule, LeaderPack, Subscription, Review


def test_user_model_fields():
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed",
        display_name="Test User",
    )
    assert user.email == "test@example.com"
    assert user.is_admin is False


def test_capsule_model_fields():
    capsule = Capsule(
        id=uuid.uuid4(),
        sieve_id=uuid.uuid4(),
        title="Test Capsule",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Full content here",
        tags=["ai", "test"],
        keywords=["artificial-intelligence"],
        topics=["technology"],
        category="AI",
        domain="technology",
        difficulty="beginner",
        content_type="insight",
        author="personal",
        capture_method="manual",
        source_type="blog",
        status="active",
        pinned=False,
        skill_eligible=True,
    )
    assert capsule.title == "Test Capsule"
    assert "ai" in capsule.tags


def test_leader_pack_model_fields():
    pack = LeaderPack(
        id=uuid.uuid4(),
        name="Andrej Karpathy",
        slug="karpathy",
        description="AI insights",
        author_url="https://karpathy.ai",
        version="1.0.0",
        topics=["ai", "ml"],
    )
    assert pack.slug == "karpathy"
    assert pack.rating_avg == 0.0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sieve.db'`

**Step 3: Create database.py**

Adapt from v2's `api/db/database.py`:

```python
# src/sieve/db/database.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sieve.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
```

**Step 4: Create models.py**

Adapt from v2's `api/db/models.py`, add v3 capsule fields:

```python
# src/sieve/db/models.py
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sieve: Mapped["Sieve"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class Sieve(Base):
    __tablename__ = "sieves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="sieve")
    capsules: Mapped[list["Capsule"]] = relationship(back_populates="sieve", cascade="all, delete-orphan")


class Capsule(Base):
    __tablename__ = "capsules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sieve_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sieves.id", ondelete="CASCADE"))

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    executive_summary: Mapped[str] = mapped_column(String(2000), default="")
    core_insight: Mapped[str] = mapped_column(String(2000), default="")
    full_content: Mapped[str] = mapped_column(Text, default="")

    # Discovery metadata (rich tagging)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    category: Mapped[str] = mapped_column(String(200), default="")
    domain: Mapped[str] = mapped_column(String(100), default="")
    difficulty: Mapped[str] = mapped_column(String(50), default="beginner")
    content_type: Mapped[str] = mapped_column(String(50), default="insight")

    # Provenance
    author: Mapped[str] = mapped_column(String(200), default="personal")
    pack_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leader_packs.id", ondelete="SET NULL"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    capture_method: Mapped[str] = mapped_column(String(50), default="manual")
    source_type: Mapped[str] = mapped_column(String(50), default="")

    # System
    status: Mapped[str] = mapped_column(String(50), default="active")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    skill_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    sieve: Mapped["Sieve"] = relationship(back_populates="capsules")
    pack: Mapped["LeaderPack | None"] = relationship(back_populates="capsules")


class LeaderPack(Base):
    __tablename__ = "leader_packs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="")
    author_url: Mapped[str] = mapped_column(String(2000), default="")
    version: Mapped[str] = mapped_column(String(50), default="1.0.0")
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    capsules: Mapped[list["Capsule"]] = relationship(back_populates="pack")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="pack", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(back_populates="pack", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "pack_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    pack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leader_packs.id", ondelete="CASCADE"), primary_key=True)
    subscribed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship()
    pack: Mapped["LeaderPack"] = relationship(back_populates="subscriptions")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "pack_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    pack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leader_packs.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[str] = mapped_column(String(2000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship()
    pack: Mapped["LeaderPack"] = relationship(back_populates="reviews")
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_db_models.py -v`
Expected: PASS (all 3 tests)

**Step 6: Set up Alembic**

Run: `cd /Users/lucasfischer/Documents/Code/neural-sieve-v3 && uv run alembic init src/sieve/db/migrations`

Then edit `alembic.ini` to set `sqlalchemy.url` and `script_location = src/sieve/db/migrations`.

Edit `env.py` to import `Base` from `sieve.db.models` and set `target_metadata = Base.metadata`.

**Step 7: Generate initial migration**

Run: `uv run alembic revision --autogenerate -m "initial schema"`

**Step 8: Commit**

```bash
git add -A
git commit -m "feat: database models for users, sieves, capsules, leader packs, subscriptions, reviews"
```

---

### Task 3: Auth System

**Files:**
- Create: `src/sieve/api/__init__.py`
- Create: `src/sieve/api/app.py`
- Create: `src/sieve/api/auth/__init__.py`
- Create: `src/sieve/api/auth/deps.py`
- Create: `src/sieve/api/auth/routes.py`
- Create: `src/sieve/api/auth/schemas.py`
- Test: `tests/test_auth.py`

**Step 1: Write failing tests for auth**

```python
# tests/test_auth.py
from sieve.api.auth.deps import hash_password, verify_password, create_access_token, verify_token


def test_password_hashing():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip():
    import uuid
    user_id = uuid.uuid4()
    token = create_access_token(str(user_id))
    decoded_id = verify_token(token)
    assert decoded_id == str(user_id)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement auth deps**

Adapt from v2's `api/auth/deps.py`:

```python
# src/sieve/api/auth/deps.py
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = verify_token(credentials.credentials)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_user_by_api_key(
    api_key: str,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user
```

**Step 4: Implement auth routes**

```python
# src/sieve/api/auth/schemas.py
from pydantic import BaseModel, EmailStr


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    api_key: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    api_key: str
```

```python
# src/sieve/api/auth/routes.py
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.db.database import get_db
from sieve.db.models import User, Sieve
from sieve.api.auth.deps import hash_password, verify_password, create_access_token, get_current_user
from sieve.api.auth.schemas import SignupRequest, LoginRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=TokenResponse)
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.flush()

    sieve = Sieve(user_id=user.id, name=f"{req.display_name}'s Sieve")
    db.add(sieve)
    await db.commit()

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, api_key=str(user.api_key))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, api_key=str(user.api_key))


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        api_key=str(user.api_key),
    )
```

**Step 5: Create FastAPI app**

```python
# src/sieve/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sieve.api.auth.routes import router as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="Neural Sieve v3", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)

    return app


app = create_app()
```

**Step 6: Add `serve` CLI command**

Add to `src/sieve/cli.py`:

```python
@cli.command()
@click.option("--port", default=8421)
def serve(port):
    """Start the API server."""
    import uvicorn
    from sieve.config import settings
    uvicorn.run("sieve.api.app:app", host=settings.host, port=port, reload=True)
```

**Step 7: Run tests**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS

**Step 8: Commit**

```bash
git add -A
git commit -m "feat: auth system with JWT, API key, signup/login endpoints"
```

---

### Task 4: Capsule CRUD + Search API

**Files:**
- Create: `src/sieve/api/capsules/__init__.py`
- Create: `src/sieve/api/capsules/routes.py`
- Create: `src/sieve/api/capsules/schemas.py`
- Create: `src/sieve/llm/__init__.py`
- Create: `src/sieve/llm/client.py`
- Create: `src/sieve/llm/prompts.py`
- Create: `src/sieve/api/capture/__init__.py`
- Create: `src/sieve/api/capture/routes.py`
- Create: `src/sieve/api/capture/pipeline.py`
- Create: `src/sieve/api/capture/scraper.py`
- Test: `tests/test_capsules.py`
- Test: `tests/test_capture.py`

**Step 1: Write failing tests for capsule schemas**

```python
# tests/test_capsules.py
from sieve.api.capsules.schemas import CapsuleResponse, CapsuleCreate


def test_capsule_create_schema():
    data = CapsuleCreate(
        title="Test",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        tags=["ai"],
        keywords=["artificial-intelligence"],
        topics=["technology"],
        category="AI",
        domain="technology",
    )
    assert data.title == "Test"
    assert data.tags == ["ai"]


def test_capsule_response_schema():
    import uuid
    resp = CapsuleResponse(
        id=str(uuid.uuid4()),
        title="Test",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        tags=["ai"],
        keywords=["artificial-intelligence"],
        topics=["technology"],
        category="AI",
        domain="technology",
        difficulty="beginner",
        content_type="insight",
        author="personal",
        source_url=None,
        capture_method="manual",
        source_type="blog",
        status="active",
        pinned=False,
        skill_eligible=True,
        created_at="2026-03-01T00:00:00",
    )
    assert resp.title == "Test"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_capsules.py -v`
Expected: FAIL

**Step 3: Implement capsule schemas**

```python
# src/sieve/api/capsules/schemas.py
from pydantic import BaseModel


class CapsuleCreate(BaseModel):
    title: str
    executive_summary: str = ""
    core_insight: str = ""
    full_content: str = ""
    tags: list[str] = []
    keywords: list[str] = []
    topics: list[str] = []
    category: str = ""
    domain: str = ""
    difficulty: str = "beginner"
    content_type: str = "insight"
    author: str = "personal"
    source_url: str | None = None
    capture_method: str = "manual"
    source_type: str = ""
    pinned: bool = False
    skill_eligible: bool = True


class CapsuleUpdate(BaseModel):
    title: str | None = None
    executive_summary: str | None = None
    core_insight: str | None = None
    full_content: str | None = None
    tags: list[str] | None = None
    keywords: list[str] | None = None
    topics: list[str] | None = None
    category: str | None = None
    domain: str | None = None
    difficulty: str | None = None
    content_type: str | None = None
    pinned: bool | None = None
    skill_eligible: bool | None = None
    status: str | None = None


class CapsuleResponse(BaseModel):
    id: str
    title: str
    executive_summary: str
    core_insight: str
    full_content: str
    tags: list[str]
    keywords: list[str]
    topics: list[str]
    category: str
    domain: str
    difficulty: str
    content_type: str
    author: str
    source_url: str | None
    capture_method: str
    source_type: str
    status: str
    pinned: bool
    skill_eligible: bool
    created_at: str


class CapsuleListResponse(BaseModel):
    capsules: list[CapsuleResponse]
    total: int


class CaptureRequest(BaseModel):
    content: str = ""
    url: str | None = None
    source_url: str | None = None
    images: list[str] = []  # base64 encoded


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    category: str | None = None
    domain: str | None = None
    difficulty: str | None = None
    author: str | None = None
    pack: str | None = None
```

**Step 4: Implement capsule CRUD routes**

```python
# src/sieve/api/capsules/routes.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.db.database import get_db
from sieve.db.models import User, Sieve, Capsule
from sieve.api.auth.deps import get_current_user
from sieve.api.capsules.schemas import (
    CapsuleCreate, CapsuleUpdate, CapsuleResponse, CapsuleListResponse, SearchRequest,
)

router = APIRouter(prefix="/api/capsules", tags=["capsules"])


def capsule_to_response(c: Capsule) -> CapsuleResponse:
    return CapsuleResponse(
        id=str(c.id),
        title=c.title,
        executive_summary=c.executive_summary,
        core_insight=c.core_insight,
        full_content=c.full_content,
        tags=c.tags or [],
        keywords=c.keywords or [],
        topics=c.topics or [],
        category=c.category,
        domain=c.domain,
        difficulty=c.difficulty,
        content_type=c.content_type,
        author=c.author,
        source_url=c.source_url,
        capture_method=c.capture_method,
        source_type=c.source_type,
        status=c.status,
        pinned=c.pinned,
        skill_eligible=c.skill_eligible,
        created_at=c.created_at.isoformat() if c.created_at else "",
    )


@router.get("/", response_model=CapsuleListResponse)
async def list_capsules(
    search: str | None = Query(None),
    category: str | None = Query(None),
    domain: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = sieve.scalar_one()

    query = select(Capsule).where(Capsule.sieve_id == sieve.id, Capsule.status == "active")

    if category:
        query = query.where(Capsule.category == category)
    if domain:
        query = query.where(Capsule.domain == domain)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    query = query.order_by(Capsule.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    capsules = result.scalars().all()

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=total,
    )


@router.post("/", status_code=201, response_model=CapsuleResponse)
async def create_capsule(
    data: CapsuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = sieve.scalar_one()

    capsule = Capsule(sieve_id=sieve.id, **data.model_dump())
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)
    return capsule_to_response(capsule)


@router.get("/{capsule_id}", response_model=CapsuleResponse)
async def get_capsule(
    capsule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = sieve.scalar_one()

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")
    return capsule_to_response(capsule)


@router.put("/{capsule_id}", response_model=CapsuleResponse)
async def update_capsule(
    capsule_id: str,
    data: CapsuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = sieve.scalar_one()

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(capsule, key, value)

    await db.commit()
    await db.refresh(capsule)
    return capsule_to_response(capsule)


@router.delete("/{capsule_id}", status_code=204)
async def delete_capsule(
    capsule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = sieve.scalar_one()

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()
    if not capsule:
        raise HTTPException(status_code=404, detail="Capsule not found")

    await db.delete(capsule)
    await db.commit()


@router.post("/search", response_model=CapsuleListResponse)
async def search_capsules(
    req: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = sieve.scalar_one()

    # Basic keyword search across title, tags, keywords, full_content
    # TODO: Replace with pgvector semantic search in later task
    query = select(Capsule).where(
        Capsule.sieve_id == sieve.id,
        Capsule.status == "active",
    )

    if req.category:
        query = query.where(Capsule.category == req.category)
    if req.domain:
        query = query.where(Capsule.domain == req.domain)

    # Simple text search for now
    search_term = f"%{req.query}%"
    query = query.where(
        Capsule.title.ilike(search_term)
        | Capsule.full_content.ilike(search_term)
        | Capsule.category.ilike(search_term)
    )

    query = query.order_by(Capsule.created_at.desc()).limit(req.limit)
    result = await db.execute(query)
    capsules = result.scalars().all()

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=len(capsules),
    )
```

**Step 5: Implement capture pipeline**

Adapt from v2's `api/capture/pipeline.py` and `api/capture/scraper.py`:

```python
# src/sieve/api/capture/routes.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.db.database import get_db
from sieve.db.models import User, Sieve, Capsule
from sieve.api.auth.deps import get_current_user
from sieve.api.capsules.schemas import CaptureRequest, CapsuleResponse
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capture.pipeline import CapturePipeline

router = APIRouter(prefix="/api/capture", tags=["capture"])


@router.post("/", status_code=201, response_model=CapsuleResponse)
async def capture(
    req: CaptureRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve_result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = sieve_result.scalar_one()

    pipeline = CapturePipeline()
    capsule_data = await pipeline.process(req)

    capsule = Capsule(sieve_id=sieve.id, **capsule_data)
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)
    return capsule_to_response(capsule)
```

```python
# src/sieve/api/capture/pipeline.py
from sieve.api.capsules.schemas import CaptureRequest
from sieve.api.capture.scraper import fetch_url, extract_text_from_html
from sieve.llm.client import LLMClient


class CapturePipeline:
    def __init__(self):
        self.llm = LLMClient()

    async def process(self, req: CaptureRequest) -> dict:
        content = req.content

        if req.url:
            html = await fetch_url(req.url)
            content = extract_text_from_html(html)

        result = await self.llm.extract_capsule(content)
        result["source_url"] = req.source_url or req.url
        result["capture_method"] = "url" if req.url else "manual"

        return result
```

```python
# src/sieve/api/capture/scraper.py
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254", "metadata.google.internal"}
STRIP_TAGS = {"script", "style", "nav", "footer", "header", "aside"}


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid scheme: {parsed.scheme}")
    if parsed.hostname in BLOCKED_HOSTS:
        raise ValueError(f"Blocked host: {parsed.hostname}")
    return url


async def fetch_url(url: str) -> str:
    url = validate_url(url)
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url, headers={"User-Agent": "NeuralSieve/3.0"})
        resp.raise_for_status()
        return resp.text


def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)
```

**Step 6: Implement LLM client**

Adapt from v1's `llm/openai.py` and v2's `llm/client.py`:

```python
# src/sieve/llm/client.py
import json

from openai import AsyncOpenAI

from sieve.config import settings
from sieve.llm.prompts import CAPSULE_EXTRACTION_PROMPT


class LLMClient:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def extract_capsule(self, content: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": CAPSULE_EXTRACTION_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        result["full_content"] = content
        return result

    async def rank_capsules(self, query: str, capsules: list[dict]) -> list[dict]:
        """Rank capsules by relevance to query. Returns list with scores."""
        summaries = []
        for i, c in enumerate(capsules):
            tags = ", ".join(c.get("tags", []))
            summaries.append(f"{i}: {c['title']} [{c.get('category', '')}] (tags: {tags})")

        prompt = f"""Rate each capsule's relevance to the query on a 0-10 scale.
Return JSON array of objects with "index" and "score" fields.

Query: {query}

Capsules:
{chr(10).join(summaries)}"""

        response = await self.client.chat.completions.create(
            model=settings.search_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        scores = result.get("scores", result.get("results", []))
        return scores
```

```python
# src/sieve/llm/prompts.py
CAPSULE_EXTRACTION_PROMPT = """You are a knowledge extraction engine. Given raw text content, extract a structured knowledge capsule.

Return a JSON object with these fields:
- title: 5-10 word title capturing the main idea
- executive_summary: 2 sentences max — the hook explaining why this matters
- core_insight: Single "Aha!" moment — what makes this actionable
- tags: 5-10 specific topic tags (lowercase, hyphenated)
- keywords: 5-10 semantic search terms (lowercase, hyphenated)
- topics: 2-5 broad theme categories (lowercase, hyphenated)
- category: Specific domain (e.g., "AI Architecture" not just "Technology")
- domain: Broad domain (technology, business, science, philosophy, etc.)
- difficulty: beginner, intermediate, or advanced
- content_type: insight, tutorial, opinion, research, or case-study
- source_type: twitter, blog, video, paper, book, podcast, or other

Be precise with tags — use specific concepts, not generic ones.
Keywords should capture semantic meaning for search discovery.
"""

IMAGE_DESCRIPTION_PROMPT = """Describe this image in detail. Extract all text, code, diagrams, and formulas.
Transcribe text VERBATIM — do not summarize."""
```

**Step 7: Register new routes in app.py**

Update `src/sieve/api/app.py` to include:

```python
from sieve.api.capsules.routes import router as capsules_router
from sieve.api.capture.routes import router as capture_router

# In create_app():
app.include_router(capsules_router)
app.include_router(capture_router)
```

**Step 8: Run tests**

Run: `uv run pytest tests/test_capsules.py -v`
Expected: PASS

**Step 9: Commit**

```bash
git add -A
git commit -m "feat: capsule CRUD, search, and capture pipeline with LLM extraction"
```

---

### Task 5: MCP Server (Cloud-Connected)

**Files:**
- Create: `src/sieve/mcp/__init__.py`
- Create: `src/sieve/mcp/server.py`
- Create: `src/sieve/mcp/api_client.py`
- Test: `tests/test_mcp.py`

**Step 1: Write failing test**

```python
# tests/test_mcp.py
from sieve.mcp.api_client import SieveAPIClient


def test_api_client_init():
    client = SieveAPIClient(api_url="http://localhost:8421", api_key="test-key")
    assert client.api_url == "http://localhost:8421"
    assert client.api_key == "test-key"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: FAIL

**Step 3: Implement API client for MCP server**

```python
# src/sieve/mcp/api_client.py
import httpx


class SieveAPIClient:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def search_capsules(self, query: str, limit: int = 10, **filters) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.api_url}/api/capsules/search",
                json={"query": query, "limit": limit, **filters},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_capsule(self, capsule_id: str) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/capsules/{capsule_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def list_capsules(self, **params) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/capsules/",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_pinned(self) -> dict:
        return await self.list_capsules(pinned=True)

    async def get_index(self) -> dict:
        return await self.list_capsules(limit=200)
```

**Step 4: Implement MCP server**

Adapt from v1's `mcp/server.py`:

```python
# src/sieve/mcp/server.py
import os

from mcp.server import Server
from mcp.types import TextContent, Tool

from sieve.mcp.api_client import SieveAPIClient

server = Server("neural-sieve")


def get_client() -> SieveAPIClient:
    return SieveAPIClient(
        api_url=os.environ.get("SIEVE_API_URL", "http://localhost:8421"),
        api_key=os.environ.get("SIEVE_API_KEY", ""),
    )


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="search_capsules",
            description="Search your knowledge base. Uses semantic matching to find conceptually related capsules.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (2-4 key concepts)"},
                    "limit": {"type": "integer", "description": "Max results (default 10)", "default": 10},
                    "category": {"type": "string", "description": "Filter by category"},
                    "domain": {"type": "string", "description": "Filter by domain"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_capsule",
            description="Get a specific capsule by ID.",
            inputSchema={
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Capsule ID"}},
                "required": ["id"],
            },
        ),
        Tool(
            name="get_pinned",
            description="Get all pinned capsules (Eternal Truths). High-priority knowledge.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_index",
            description="Get the full knowledge index showing all capsules.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    client = get_client()

    if name == "search_capsules":
        result = await client.search_capsules(
            query=arguments["query"],
            limit=arguments.get("limit", 10),
            category=arguments.get("category"),
            domain=arguments.get("domain"),
        )
        return [TextContent(type="text", text=format_capsule_list(result))]

    elif name == "get_capsule":
        capsule = await client.get_capsule(arguments["id"])
        return [TextContent(type="text", text=format_capsule(capsule))]

    elif name == "get_pinned":
        result = await client.get_pinned()
        return [TextContent(type="text", text=format_capsule_list(result))]

    elif name == "get_index":
        result = await client.get_index()
        return [TextContent(type="text", text=format_index(result))]


def format_capsule(c: dict) -> str:
    tags = ", ".join(c.get("tags", []))
    return f"""# {c['title']}
**Category:** {c.get('category', '')} | **Domain:** {c.get('domain', '')} | **Tags:** {tags}

## Executive Summary
{c.get('executive_summary', '')}

## Core Insight
{c.get('core_insight', '')}

## Full Content
{c.get('full_content', '')}"""


def format_capsule_list(data: dict) -> str:
    capsules = data.get("capsules", [])
    if not capsules:
        return "No capsules found."
    lines = [f"Found {len(capsules)} capsules:\n"]
    for c in capsules:
        tags = ", ".join(c.get("tags", [])[:5])
        lines.append(f"- **{c['title']}** [{c.get('category', '')}] (tags: {tags}) [ID: {c['id']}]")
    return "\n".join(lines)


def format_index(data: dict) -> str:
    capsules = data.get("capsules", [])
    categories = {}
    for c in capsules:
        cat = c.get("category", "Uncategorized")
        categories.setdefault(cat, []).append(c)

    lines = ["# Knowledge Index\n"]
    for cat, caps in sorted(categories.items()):
        lines.append(f"\n## {cat} ({len(caps)} capsules)")
        for c in caps:
            lines.append(f"- {c['title']} [ID: {c['id']}]")
    return "\n".join(lines)


async def run_server():
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
```

**Step 5: Add `mcp` CLI command**

Add to `src/sieve/cli.py`:

```python
@cli.command()
def mcp():
    """Start MCP server for Claude Code integration."""
    import asyncio
    from sieve.mcp.server import run_server
    asyncio.run(run_server())
```

**Step 6: Run test**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: MCP server connecting to cloud API with search, get, pinned, index tools"
```

---

### Task 6: Skill Compiler CLI

**Files:**
- Create: `src/sieve/compiler/__init__.py`
- Create: `src/sieve/compiler/compiler.py`
- Create: `src/sieve/compiler/templates.py`
- Test: `tests/test_compiler.py`

**Step 1: Write failing test**

```python
# tests/test_compiler.py
from sieve.compiler.compiler import SkillCompiler
from sieve.compiler.templates import SKILL_TEMPLATE


def test_skill_template_renders():
    rendered = SKILL_TEMPLATE.format(
        name="test-skill",
        description="A test skill",
        body="## Principles\n1. Be simple\n2. Ship fast",
    )
    assert "name: test-skill" in rendered
    assert "## Principles" in rendered


def test_compiler_group_by_author():
    capsules = [
        {"author": "karpathy", "title": "A", "tags": ["ai"]},
        {"author": "karpathy", "title": "B", "tags": ["ml"]},
        {"author": "personal", "title": "C", "tags": ["dev"]},
    ]
    compiler = SkillCompiler(api_url="http://localhost:8421", api_key="test")
    groups = compiler.group_capsules(capsules, by="author")
    assert "karpathy" in groups
    assert len(groups["karpathy"]) == 2
    assert "personal" in groups
    assert len(groups["personal"]) == 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_compiler.py -v`
Expected: FAIL

**Step 3: Implement skill template**

```python
# src/sieve/compiler/templates.py
SKILL_TEMPLATE = """---
name: {name}
description: {description}
---

{body}
"""

COMPILE_PROMPT = """You are a skill compiler. Given a collection of knowledge capsules from {author}, distill them into a concise Claude Code skill file.

The skill should contain:
1. Core principles (numbered list of actionable rules)
2. Domain-specific guidance organized by topic
3. Anti-patterns to avoid

Be concise. Each principle should be 1-2 sentences. Organize by topic when there are enough capsules.
Output only the skill body content (markdown), no frontmatter.

Capsules:
{capsules_text}"""
```

**Step 4: Implement compiler**

```python
# src/sieve/compiler/compiler.py
import os
from pathlib import Path

from sieve.mcp.api_client import SieveAPIClient
from sieve.llm.client import LLMClient
from sieve.compiler.templates import SKILL_TEMPLATE, COMPILE_PROMPT


class SkillCompiler:
    def __init__(self, api_url: str, api_key: str):
        self.api_client = SieveAPIClient(api_url=api_url, api_key=api_key)
        self.llm = LLMClient()

    def group_capsules(self, capsules: list[dict], by: str = "author") -> dict[str, list[dict]]:
        groups: dict[str, list[dict]] = {}
        for c in capsules:
            key = c.get(by, "unknown")
            groups.setdefault(key, []).append(c)
        return groups

    async def compile_group(self, author: str, capsules: list[dict]) -> str:
        capsules_text = ""
        for c in capsules:
            tags = ", ".join(c.get("tags", []))
            capsules_text += f"\n### {c['title']}\nTags: {tags}\n"
            capsules_text += f"Insight: {c.get('core_insight', '')}\n"
            capsules_text += f"Summary: {c.get('executive_summary', '')}\n"

        prompt = COMPILE_PROMPT.format(author=author, capsules_text=capsules_text)
        response = await self.llm.client.chat.completions.create(
            model=self.llm.model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    async def compile_to_skills(
        self,
        output_dir: Path,
        pack: str | None = None,
        personal: bool = False,
        all_capsules: bool = False,
    ) -> list[Path]:
        data = await self.api_client.list_capsules(limit=200)
        capsules = data.get("capsules", [])

        if pack:
            capsules = [c for c in capsules if c.get("author") == pack]
        elif personal:
            capsules = [c for c in capsules if c.get("author") == "personal"]

        groups = self.group_capsules(capsules, by="author")
        output_dir.mkdir(parents=True, exist_ok=True)
        written = []

        for author, group in groups.items():
            if len(group) < 2:
                continue

            body = await self.compile_group(author, group)
            slug = author.lower().replace(" ", "-")
            name = f"sieve-{slug}"
            description = f"Knowledge and principles from {author} ({len(group)} capsules)"

            skill_content = SKILL_TEMPLATE.format(name=name, description=description, body=body)
            path = output_dir / f"{name}.md"
            path.write_text(skill_content)
            written.append(path)

        return written
```

**Step 5: Add `compile` CLI command**

Add to `src/sieve/cli.py`:

```python
@cli.command()
@click.option("--pack", help="Compile a specific leader pack")
@click.option("--personal", is_flag=True, help="Compile personal capsules only")
@click.option("--all", "all_capsules", is_flag=True, help="Compile everything")
@click.option("--output", default=".claude/skills", help="Output directory")
def compile(pack, personal, all_capsules, output):
    """Compile capsules into Claude Code skill files."""
    import asyncio
    from pathlib import Path
    from sieve.config import settings
    from sieve.compiler.compiler import SkillCompiler

    compiler = SkillCompiler(api_url=settings.sieve_api_url, api_key=settings.sieve_api_key)
    paths = asyncio.run(
        compiler.compile_to_skills(
            output_dir=Path(output),
            pack=pack,
            personal=personal,
            all_capsules=all_capsules,
        )
    )
    for p in paths:
        click.echo(f"Generated: {p}")
    click.echo(f"\n{len(paths)} skill(s) compiled.")
```

**Step 6: Run test**

Run: `uv run pytest tests/test_compiler.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: skill compiler CLI - capsules to .claude/skills/*.md"
```

---

### Task 7: Basic Web Dashboard (My Sieve + Capture)

**Files:**
- Create: `src/sieve/dashboard/__init__.py`
- Create: `src/sieve/dashboard/routes.py`
- Create: `src/sieve/dashboard/templates/base.html`
- Create: `src/sieve/dashboard/templates/login.html`
- Create: `src/sieve/dashboard/templates/sieve.html`
- Create: `src/sieve/dashboard/templates/capture.html`
- Create: `src/sieve/dashboard/static/style.css`
- Modify: `src/sieve/api/app.py` (add dashboard routes + static/templates)

**Step 1: Write failing test**

```python
# tests/test_dashboard.py
def test_dashboard_routes_exist():
    from sieve.dashboard.routes import router
    paths = [r.path for r in router.routes]
    assert "/" in paths or "/sieve" in paths
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: FAIL

**Step 3: Create base template**

```html
<!-- src/sieve/dashboard/templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Neural Sieve{% endblock %}</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <link rel="manifest" href="/static/manifest.json">
</head>
<body>
    <nav class="nav">
        <a href="/" class="nav-brand">Neural Sieve</a>
        <div class="nav-links">
            <a href="/sieve" hx-boost="true">My Sieve</a>
            <a href="/capture" hx-boost="true">Capture</a>
            <a href="/discover" hx-boost="true">Discover</a>
            <a href="/compile" hx-boost="true">Compile</a>
            <a href="/settings" hx-boost="true">Settings</a>
        </div>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

**Step 4: Create sieve page (My Sieve)**

```html
<!-- src/sieve/dashboard/templates/sieve.html -->
{% extends "base.html" %}
{% block title %}My Sieve — Neural Sieve{% endblock %}
{% block content %}
<div class="sieve-page">
    <div class="sieve-header">
        <h1>My Sieve</h1>
        <div class="search-bar">
            <input type="search" name="q" placeholder="Search capsules..."
                   hx-get="/sieve/search" hx-trigger="keyup changed delay:300ms"
                   hx-target="#capsule-list">
        </div>
    </div>

    <div class="filters">
        <select hx-get="/sieve/filter" hx-target="#capsule-list" name="category">
            <option value="">All Categories</option>
            {% for cat in categories %}
            <option value="{{ cat }}">{{ cat }}</option>
            {% endfor %}
        </select>
        <select hx-get="/sieve/filter" hx-target="#capsule-list" name="domain">
            <option value="">All Domains</option>
            {% for d in domains %}
            <option value="{{ d }}">{{ d }}</option>
            {% endfor %}
        </select>
    </div>

    <div id="capsule-list" class="capsule-grid">
        {% for capsule in capsules %}
        <div class="capsule-card" onclick="location.href='/capsule/{{ capsule.id }}'">
            <span class="capsule-category">{{ capsule.category }}</span>
            <h3>{{ capsule.title }}</h3>
            <p>{{ capsule.executive_summary }}</p>
            <div class="capsule-tags">
                {% for tag in capsule.tags[:5] %}
                <span class="tag">{{ tag }}</span>
                {% endfor %}
            </div>
            <div class="capsule-meta">
                {{ capsule.domain }} · {{ capsule.difficulty }} · {{ capsule.created_at[:10] }}
                {% if capsule.pinned %}<span class="pin">pinned</span>{% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
```

**Step 5: Create capture page**

```html
<!-- src/sieve/dashboard/templates/capture.html -->
{% extends "base.html" %}
{% block title %}Capture — Neural Sieve{% endblock %}
{% block content %}
<div class="capture-page">
    <h1>Quick Capture</h1>
    <form hx-post="/capture/submit" hx-target="#capture-result" class="capture-form">
        <div class="form-group">
            <label>URL (optional)</label>
            <input type="url" name="url" placeholder="https://...">
        </div>
        <div class="form-group">
            <label>Content</label>
            <textarea name="content" rows="8" placeholder="Paste text, notes, or insights..."></textarea>
        </div>
        <button type="submit" class="btn-primary">Capture</button>
    </form>
    <div id="capture-result"></div>
</div>
{% endblock %}
```

**Step 6: Create dashboard routes**

```python
# src/sieve/dashboard/routes.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("sieve.html", {
        "request": request,
        "capsules": [],
        "categories": [],
        "domains": [],
    })


@router.get("/sieve", response_class=HTMLResponse)
async def sieve_page(request: Request):
    return templates.TemplateResponse("sieve.html", {
        "request": request,
        "capsules": [],
        "categories": [],
        "domains": [],
    })


@router.get("/capture", response_class=HTMLResponse)
async def capture_page(request: Request):
    return templates.TemplateResponse("capture.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
```

**Step 7: Create minimal CSS**

```css
/* src/sieve/dashboard/static/style.css */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, system-ui, sans-serif; background: #0a0a0a; color: #e5e5e5; }
.container { max-width: 1200px; margin: 0 auto; padding: 1rem; }
.nav { display: flex; justify-content: space-between; align-items: center; padding: 1rem 2rem; border-bottom: 1px solid #222; }
.nav-brand { font-size: 1.25rem; font-weight: 700; color: #fff; text-decoration: none; }
.nav-links { display: flex; gap: 1.5rem; }
.nav-links a { color: #888; text-decoration: none; font-size: 0.875rem; }
.nav-links a:hover { color: #fff; }

.sieve-header { display: flex; justify-content: space-between; align-items: center; margin: 2rem 0; }
.search-bar input { background: #1a1a1a; border: 1px solid #333; color: #fff; padding: 0.5rem 1rem; border-radius: 6px; width: 300px; }
.filters { display: flex; gap: 1rem; margin-bottom: 1.5rem; }
.filters select { background: #1a1a1a; border: 1px solid #333; color: #fff; padding: 0.4rem 0.8rem; border-radius: 6px; }

.capsule-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 1rem; }
.capsule-card { background: #141414; border: 1px solid #222; border-radius: 8px; padding: 1.25rem; cursor: pointer; transition: border-color 0.2s; }
.capsule-card:hover { border-color: #444; }
.capsule-category { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; }
.capsule-card h3 { margin: 0.5rem 0; font-size: 1rem; color: #fff; }
.capsule-card p { font-size: 0.875rem; color: #999; line-height: 1.4; }
.capsule-tags { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.75rem; }
.tag { font-size: 0.7rem; background: #1a1a2e; color: #6366f1; padding: 0.15rem 0.5rem; border-radius: 4px; }
.capsule-meta { font-size: 0.75rem; color: #666; margin-top: 0.75rem; }
.pin { color: #f59e0b; }

.capture-form { max-width: 600px; }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; margin-bottom: 0.4rem; font-size: 0.875rem; color: #888; }
.form-group input, .form-group textarea { width: 100%; background: #1a1a1a; border: 1px solid #333; color: #fff; padding: 0.6rem; border-radius: 6px; }
.btn-primary { background: #6366f1; color: #fff; border: none; padding: 0.6rem 1.5rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
.btn-primary:hover { background: #5558e6; }

@media (max-width: 768px) {
    .nav { flex-direction: column; gap: 0.75rem; }
    .sieve-header { flex-direction: column; gap: 1rem; }
    .search-bar input { width: 100%; }
    .capsule-grid { grid-template-columns: 1fr; }
}
```

**Step 8: Mount dashboard in app.py**

Update `src/sieve/api/app.py`:

```python
from fastapi.staticfiles import StaticFiles
from sieve.dashboard.routes import router as dashboard_router

# In create_app():
app.mount("/static", StaticFiles(directory="src/sieve/dashboard/static"), name="static")
app.include_router(dashboard_router)
```

**Step 9: Run test**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: PASS

**Step 10: Commit**

```bash
git add -A
git commit -m "feat: web dashboard with My Sieve and Capture pages (HTMX + dark theme)"
```

---

### Task 8: V1 Capsule Migration Script

**Files:**
- Create: `scripts/migrate_v1.py`
- Test: `tests/test_migration.py`

**Step 1: Write failing test**

```python
# tests/test_migration.py
from sieve.compiler.templates import SKILL_TEMPLATE  # just to verify imports work


def test_parse_v1_capsule():
    from scripts.migrate_v1 import parse_v1_capsule

    v1_content = """---
id: 2026-01-22-T095249-3306
title: AI Agent Unlocks Paid Data
source_url: https://example.com
tags:
- AI agents
- Data access
category: AI Agents
status: active
pinned: false
captured_at: '2026-01-22'
capture_method: browser
---

# Executive Summary

> Test summary.

# Core Insight

Test insight.

# Full Content

Full content here.
"""
    result = parse_v1_capsule(v1_content)
    assert result["title"] == "AI Agent Unlocks Paid Data"
    assert "AI agents" in result["tags"]
    assert result["executive_summary"] == "Test summary."
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_migration.py -v`
Expected: FAIL

**Step 3: Implement migration script**

```python
# scripts/migrate_v1.py
"""Migrate Neural Sieve v1 capsules to v3 cloud backend."""
import re
import asyncio
from pathlib import Path

import frontmatter
import httpx


V1_CAPSULES_DIR = Path("/Users/lucasfischer/Documents/Code/sieve_ideas/neural-sieve/Capsules")


def parse_v1_capsule(content: str) -> dict:
    """Parse a v1 capsule markdown file into v3 format."""
    post = frontmatter.loads(content)
    meta = post.metadata

    # Extract sections from body
    body = post.content
    exec_summary = ""
    core_insight = ""
    full_content = ""

    # Parse sections
    sections = re.split(r"^# ", body, flags=re.MULTILINE)
    for section in sections:
        if section.startswith("Executive Summary"):
            text = section.replace("Executive Summary", "").strip()
            exec_summary = text.lstrip("> ").strip()
        elif section.startswith("Core Insight"):
            core_insight = section.replace("Core Insight", "").strip()
        elif section.startswith("Full Content"):
            full_content = section.replace("Full Content", "").strip()

    return {
        "title": meta.get("title", ""),
        "executive_summary": exec_summary,
        "core_insight": core_insight,
        "full_content": full_content,
        "tags": meta.get("tags", []),
        "keywords": [],  # v1 didn't have keywords
        "topics": [],  # v1 didn't have topics
        "category": meta.get("category", ""),
        "domain": "",  # v1 didn't have domain
        "difficulty": "intermediate",
        "content_type": "insight",
        "author": "personal",
        "source_url": meta.get("source_url"),
        "capture_method": meta.get("capture_method", "manual"),
        "source_type": "",
        "status": meta.get("status", "active"),
        "pinned": meta.get("pinned", False),
        "skill_eligible": True,
    }


async def migrate(api_url: str, api_key: str):
    """Migrate all v1 capsules to v3 cloud backend."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    migrated = 0
    errors = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for md_file in V1_CAPSULES_DIR.rglob("*.md"):
            if md_file.name == "INDEX.md":
                continue
            try:
                content = md_file.read_text()
                capsule_data = parse_v1_capsule(content)
                resp = await client.post(
                    f"{api_url}/api/capsules/",
                    json=capsule_data,
                    headers=headers,
                )
                resp.raise_for_status()
                migrated += 1
                print(f"  Migrated: {capsule_data['title']}")
            except Exception as e:
                errors += 1
                print(f"  Error: {md_file.name} — {e}")

    print(f"\nDone. Migrated: {migrated}, Errors: {errors}")


if __name__ == "__main__":
    import sys
    api_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8421"
    api_key = sys.argv[2] if len(sys.argv) > 2 else ""
    asyncio.run(migrate(api_url, api_key))
```

**Step 4: Run test**

Run: `uv run pytest tests/test_migration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: v1 capsule migration script"
```

---

## Phase 2: Leader Packs

### Task 9: Leader Pack API

**Files:**
- Create: `src/sieve/api/packs/__init__.py`
- Create: `src/sieve/api/packs/routes.py`
- Create: `src/sieve/api/packs/schemas.py`
- Test: `tests/test_packs.py`

**Step 1: Write failing test**

```python
# tests/test_packs.py
from sieve.api.packs.schemas import PackResponse, PackCreate


def test_pack_create():
    pack = PackCreate(
        name="Andrej Karpathy",
        slug="karpathy",
        description="AI insights",
        author_url="https://karpathy.ai",
        topics=["ai", "ml"],
    )
    assert pack.slug == "karpathy"
```

**Step 2: Implement pack schemas and CRUD routes**

Includes: list packs, get pack, subscribe/unsubscribe, rate, get reviews.

Pattern follows Task 4 (capsule CRUD). Route endpoints:
- `GET /api/packs/` — list all packs with ratings
- `GET /api/packs/{slug}` — pack detail with capsules
- `POST /api/packs/{slug}/subscribe` — subscribe to pack (copies capsules to user's sieve)
- `DELETE /api/packs/{slug}/unsubscribe` — unsubscribe
- `POST /api/packs/{slug}/rate` — submit rating (1-5) + optional comment
- `GET /api/packs/{slug}/reviews` — list reviews

**Step 3: Run tests and commit**

```bash
git add -A
git commit -m "feat: leader pack API with subscribe, rate, and review"
```

---

### Task 10: Discover Page in Dashboard

**Files:**
- Create: `src/sieve/dashboard/templates/discover.html`
- Modify: `src/sieve/dashboard/routes.py` (add discover route)

Renders leader pack cards with name, description, rating, capsule count, subscribe button.
Uses HTMX for subscribe/unsubscribe actions.

**Commit:**

```bash
git commit -m "feat: discover page for browsing and subscribing to leader packs"
```

---

### Task 11: Seed First Leader Packs

**Files:**
- Create: `scripts/seed_karpathy.py`
- Create: `leader-packs/karpathy/manifest.yaml`
- Create: `leader-packs/karpathy/capsules/*.md` (5-10 curated capsules)

Curate 5-10 capsules from Karpathy's public content (blog posts, talks, tweets).
Run the seed script to populate the cloud backend.

**Commit:**

```bash
git commit -m "feat: seed Karpathy leader pack with 10 curated capsules"
```

---

## Phase 3: Obsidian Integration (Future)

### Task 12: Sieve Obsidian Plugin Scaffolding

**Files:**
- Create: `obsidian-plugin/manifest.json`
- Create: `obsidian-plugin/main.ts`
- Create: `obsidian-plugin/settings.ts`
- Create: `obsidian-plugin/package.json`

Based on `obsidian-sample-plugin` template in research folder.

### Task 13: Plugin Inbox Watcher

Watches `Inbox/` folder for new clips from Obsidian Clipper.
Sends content to cloud API for LLM processing.
Writes resulting capsule to `Capsules/<category>/`.

### Task 14: Bidirectional Vault Sync

Sync capsules between Obsidian vault and cloud backend.
Handle conflicts (last-write-wins).

---

## Phase 4: Mobile + Polish (Future)

### Task 15: PWA Manifest + Service Worker

### Task 16: Phone-Optimized Capture Form

### Task 17: Advanced Search Filters in Dashboard

### Task 18: Pack Submission Flow for Power Users

---

## MCP Configuration

After Phase 1, users configure Claude Code with:

```json
{
  "mcpServers": {
    "neural-sieve": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/neural-sieve-v3", "sieve", "mcp"],
      "env": {
        "SIEVE_API_URL": "https://your-deployment.fly.dev",
        "SIEVE_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Build Order Summary

| Task | Component | Est. Complexity |
|------|-----------|----------------|
| 1 | Project scaffolding | Low |
| 2 | Database models + migrations | Medium |
| 3 | Auth system | Medium |
| 4 | Capsule CRUD + Search + Capture | High |
| 5 | MCP Server (cloud-connected) | Medium |
| 6 | Skill Compiler CLI | Medium |
| 7 | Web Dashboard (My Sieve + Capture) | High |
| 8 | V1 Migration Script | Low |
| 9 | Leader Pack API | Medium |
| 10 | Discover Page | Medium |
| 11 | Seed Leader Packs | Low |
| 12-14 | Obsidian Plugin (Phase 3) | High |
| 15-18 | Mobile + Polish (Phase 4) | Medium |
