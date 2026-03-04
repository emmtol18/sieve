# Leaders System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a leaders directory — evolve LeaderPack into Leader with profile fields, create API/HTMX routes, update discover page with Leaders tab, add leader profile page, and extend the Clipper extension with admin-only leader management.

**Architecture:** Alembic migration renames `leader_packs` → `leaders` and adds profile columns. New API routes (`/api/leaders/`) with admin-only mutations. HTMX routes serve leader cards and capsule grids. Extension gets Twitter DOM extraction and admin-gated "Add Leader" / "Capture to Leader" UI.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async ORM, Alembic, Pydantic v2, HTMX + Jinja2, TypeScript (extension), Manifest V3.

---

## Task 1: Alembic Migration — Evolve LeaderPack → Leader

**Files:**
- Create: `src/sieve/db/migrations/versions/004_evolve_leader_pack_to_leader.py`

**Step 1: Write the migration**

```python
"""evolve_leader_pack_to_leader

Revision ID: 004
Revises: 003
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new profile columns to leader_packs
    op.add_column("leader_packs", sa.Column("avatar_url", sa.String(2000), nullable=True))
    op.add_column("leader_packs", sa.Column("bio", sa.String(500), nullable=True))
    op.add_column("leader_packs", sa.Column("expertise_domain", sa.String(100), nullable=True))
    op.add_column("leader_packs", sa.Column("twitter_url", sa.String(500), nullable=True))
    op.add_column("leader_packs", sa.Column("linkedin_url", sa.String(500), nullable=True))
    op.add_column("leader_packs", sa.Column("is_featured", sa.Boolean(), server_default="false"))
    op.add_column("leader_packs", sa.Column("capsule_count", sa.Integer(), server_default="0"))

    # Rename table leader_packs → leaders
    op.rename_table("leader_packs", "leaders")

    # Update the FK on capsules to point to new table name
    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.create_foreign_key(
        "capsules_pack_id_fkey",
        "capsules",
        "leaders",
        ["pack_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Update FKs on subscriptions
    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.create_foreign_key(
        "subscriptions_pack_id_fkey",
        "subscriptions",
        "leaders",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Update FKs on reviews
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")
    op.create_foreign_key(
        "reviews_pack_id_fkey",
        "reviews",
        "leaders",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Reverse FK changes first
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")
    op.create_foreign_key("reviews_pack_id_fkey", "reviews", "leader_packs", ["pack_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.create_foreign_key("subscriptions_pack_id_fkey", "subscriptions", "leader_packs", ["pack_id"], ["id"], ondelete="CASCADE")

    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.create_foreign_key("capsules_pack_id_fkey", "capsules", "leader_packs", ["pack_id"], ["id"], ondelete="SET NULL")

    op.rename_table("leaders", "leader_packs")

    op.drop_column("leader_packs", "capsule_count")
    op.drop_column("leader_packs", "is_featured")
    op.drop_column("leader_packs", "linkedin_url")
    op.drop_column("leader_packs", "twitter_url")
    op.drop_column("leader_packs", "expertise_domain")
    op.drop_column("leader_packs", "bio")
    op.drop_column("leader_packs", "avatar_url")
```

**Step 2: Run the migration**

Run: `uv run alembic upgrade head`
Expected: Migration applies, `leaders` table exists with new columns.

**Step 3: Commit**

```bash
git add src/sieve/db/migrations/versions/004_evolve_leader_pack_to_leader.py
git commit -m "feat: add migration to evolve leader_packs → leaders with profile columns"
```

---

## Task 2: Update SQLAlchemy Model — LeaderPack → Leader

**Files:**
- Modify: `src/sieve/db/models.py` (LeaderPack class → Leader, add new columns)

**Step 1: Write a failing test**

Create a test that uses the Leader model name and new fields.

File: `tests/test_leaders.py`

```python
import uuid

import pytest

from sieve.db.models import Leader


def test_leader_model_has_profile_fields():
    """Leader model should have avatar_url, bio, expertise_domain, twitter_url, linkedin_url."""
    leader = Leader(
        name="Andrej Karpathy",
        slug="karpathy",
        description="Former Director of AI at Tesla",
        bio="AI researcher and educator",
        expertise_domain="AI/ML",
        avatar_url="https://example.com/avatar.jpg",
        twitter_url="https://x.com/karpathy",
        linkedin_url="https://linkedin.com/in/karpathy",
        is_featured=True,
    )
    assert leader.name == "Andrej Karpathy"
    assert leader.slug == "karpathy"
    assert leader.bio == "AI researcher and educator"
    assert leader.expertise_domain == "AI/ML"
    assert leader.avatar_url == "https://example.com/avatar.jpg"
    assert leader.twitter_url == "https://x.com/karpathy"
    assert leader.linkedin_url == "https://linkedin.com/in/karpathy"
    assert leader.is_featured is True
    assert leader.capsule_count == 0


def test_leader_defaults():
    """Leader should have sensible defaults."""
    leader = Leader(name="Test", slug="test", description="Test leader")
    assert leader.is_featured is False
    assert leader.capsule_count == 0
    assert leader.rating_avg == 0.0
    assert leader.review_count == 0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_leaders.py -v`
Expected: FAIL — `ImportError: cannot import name 'Leader' from 'sieve.db.models'`

**Step 3: Update the model**

In `src/sieve/db/models.py`, rename `LeaderPack` → `Leader` and add new columns. Update `__tablename__` to `"leaders"`. Update all relationship references from `LeaderPack` to `Leader` in Capsule, Subscription, and Review models. Update the `pack` relationship names as needed.

Key changes:
- Rename class `LeaderPack` → `Leader`
- Change `__tablename__` from `"leader_packs"` to `"leaders"`
- Add columns: `avatar_url`, `bio`, `expertise_domain`, `twitter_url`, `linkedin_url`, `is_featured`, `capsule_count`
- Update `Capsule.pack` type hint: `Mapped["Leader | None"]`
- Update `Subscription.pack` type hint: `Mapped["Leader"]`
- Update `Review.pack` type hint: `Mapped["Leader"]`

**Step 4: Run tests**

Run: `uv run pytest tests/test_leaders.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass (fix any imports of `LeaderPack` in existing tests)

**Step 6: Commit**

```bash
git add src/sieve/db/models.py tests/test_leaders.py
git commit -m "feat: rename LeaderPack → Leader, add profile fields (avatar, bio, domain, socials)"
```

---

## Task 3: Admin Guard Dependency + Leader Pydantic Schemas

**Files:**
- Modify: `src/sieve/api/auth/deps.py` (add `require_admin`)
- Create: `src/sieve/api/leaders/` directory
- Create: `src/sieve/api/leaders/__init__.py`
- Create: `src/sieve/api/leaders/schemas.py`

**Step 1: Write failing tests**

File: `tests/test_leaders.py` (append)

```python
from sieve.api.leaders.schemas import LeaderCreate, LeaderResponse, LeaderUpdate


def test_leader_create_schema():
    data = LeaderCreate(
        name="Andrej Karpathy",
        slug="karpathy",
        description="AI researcher",
        bio="Former Director of AI at Tesla",
        expertise_domain="AI/ML",
        twitter_url="https://x.com/karpathy",
    )
    assert data.name == "Andrej Karpathy"
    assert data.expertise_domain == "AI/ML"


def test_leader_response_schema():
    data = LeaderResponse(
        id="abc-123",
        name="Karpathy",
        slug="karpathy",
        description="AI researcher",
        bio="Former Director of AI at Tesla",
        expertise_domain="AI/ML",
        avatar_url=None,
        twitter_url="https://x.com/karpathy",
        linkedin_url=None,
        author_url=None,
        topics=[],
        is_featured=False,
        capsule_count=5,
        created_at="2026-01-01T00:00:00Z",
    )
    assert data.capsule_count == 5


def test_leader_update_schema_all_optional():
    data = LeaderUpdate()
    assert data.name is None
    assert data.bio is None
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_leaders.py::test_leader_create_schema -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement**

Add to `src/sieve/api/auth/deps.py`:

```python
async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Require the current user to be an admin."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
```

Create `src/sieve/api/leaders/__init__.py` (empty).

Create `src/sieve/api/leaders/schemas.py`:

```python
from pydantic import BaseModel


class LeaderCreate(BaseModel):
    name: str
    slug: str
    description: str
    bio: str = ""
    expertise_domain: str = ""
    avatar_url: str | None = None
    twitter_url: str | None = None
    linkedin_url: str | None = None
    author_url: str | None = None
    topics: list[str] = []
    is_featured: bool = False


class LeaderUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    bio: str | None = None
    expertise_domain: str | None = None
    avatar_url: str | None = None
    twitter_url: str | None = None
    linkedin_url: str | None = None
    author_url: str | None = None
    topics: list[str] | None = None
    is_featured: bool | None = None


class LeaderResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    bio: str
    expertise_domain: str
    avatar_url: str | None
    twitter_url: str | None
    linkedin_url: str | None
    author_url: str | None
    topics: list[str]
    is_featured: bool
    capsule_count: int
    created_at: str


class LeaderListResponse(BaseModel):
    leaders: list[LeaderResponse]
    total: int
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_leaders.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/auth/deps.py src/sieve/api/leaders/ tests/test_leaders.py
git commit -m "feat: add require_admin dependency and Leader Pydantic schemas"
```

---

## Task 4: Leader API Routes (CRUD)

**Files:**
- Create: `src/sieve/api/leaders/routes.py`
- Modify: `src/sieve/api/app.py` (register new router)

**Step 1: Write failing tests**

File: `tests/test_leaders.py` (append integration tests using the test client)

```python
import pytest
from httpx import ASGITransport, AsyncClient

from sieve.api.app import create_app
from sieve.db.models import Leader, Sieve, User


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_list_leaders_empty(app, db_session):
    """GET /api/leaders/ returns empty list when no leaders exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/leaders/")
    assert response.status_code == 200
    data = response.json()
    assert data["leaders"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_leader_requires_admin(app, db_session, auth_headers):
    """POST /api/leaders/ should return 403 for non-admin users."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/leaders/",
            json={"name": "Test", "slug": "test", "description": "Test leader"},
            headers=auth_headers,
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_leader_as_admin(app, db_session, admin_auth_headers):
    """POST /api/leaders/ should create a leader for admin users."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/leaders/",
            json={
                "name": "Andrej Karpathy",
                "slug": "karpathy",
                "description": "AI researcher and educator",
                "bio": "Former Director of AI at Tesla",
                "expertise_domain": "AI/ML",
                "twitter_url": "https://x.com/karpathy",
            },
            headers=admin_auth_headers,
        )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Andrej Karpathy"
    assert data["slug"] == "karpathy"
    assert data["expertise_domain"] == "AI/ML"
```

Note: You may need to set up `admin_auth_headers` and `auth_headers` fixtures in `conftest.py`. The `admin_auth_headers` fixture creates a user with `is_admin=True` and returns a valid JWT Bearer header.

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_leaders.py::test_list_leaders_empty -v`
Expected: FAIL — 404 (route not registered)

**Step 3: Create the routes**

File: `src/sieve/api/leaders/routes.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user, require_admin
from sieve.api.leaders.schemas import LeaderCreate, LeaderListResponse, LeaderResponse, LeaderUpdate
from sieve.db.database import get_db
from sieve.db.models import Capsule, Leader, User

router = APIRouter(prefix="/api/leaders", tags=["leaders"])


def leader_to_response(leader: Leader) -> LeaderResponse:
    return LeaderResponse(
        id=str(leader.id),
        name=leader.name,
        slug=leader.slug,
        description=leader.description,
        bio=leader.bio or "",
        expertise_domain=leader.expertise_domain or "",
        avatar_url=leader.avatar_url,
        twitter_url=leader.twitter_url,
        linkedin_url=leader.linkedin_url,
        author_url=leader.author_url,
        topics=leader.topics or [],
        is_featured=leader.is_featured,
        capsule_count=leader.capsule_count,
        created_at=leader.created_at.isoformat() if leader.created_at else "",
    )


@router.get("/", response_model=LeaderListResponse)
async def list_leaders(
    domain: str | None = Query(None, description="Filter by expertise_domain"),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all leaders. Public endpoint (no auth required)."""
    query = select(Leader)

    if domain:
        query = query.where(Leader.expertise_domain == domain)
    if search:
        term = f"%{search}%"
        query = query.where(
            Leader.name.ilike(term) | Leader.description.ilike(term) | Leader.bio.ilike(term)
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Leader.is_featured.desc(), Leader.name.asc()).limit(200)
    result = await db.execute(query)
    leaders = result.scalars().all()

    return LeaderListResponse(
        leaders=[leader_to_response(l) for l in leaders],
        total=total,
    )


@router.get("/{slug}", response_model=LeaderResponse)
async def get_leader(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a leader by slug. Public endpoint."""
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")
    return leader_to_response(leader)


@router.post("/", response_model=LeaderResponse, status_code=status.HTTP_201_CREATED)
async def create_leader(
    body: LeaderCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new leader. Admin only."""
    # Check slug uniqueness
    existing = await db.execute(select(Leader).where(Leader.slug == body.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Leader with this slug already exists")

    leader = Leader(
        name=body.name,
        slug=body.slug,
        description=body.description,
        bio=body.bio,
        expertise_domain=body.expertise_domain,
        avatar_url=body.avatar_url,
        twitter_url=body.twitter_url,
        linkedin_url=body.linkedin_url,
        author_url=body.author_url,
        topics=body.topics,
        is_featured=body.is_featured,
    )
    db.add(leader)
    await db.commit()
    await db.refresh(leader)
    return leader_to_response(leader)


@router.put("/{slug}", response_model=LeaderResponse)
async def update_leader(
    slug: str,
    body: LeaderUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a leader. Admin only."""
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(leader, key, value)

    await db.commit()
    await db.refresh(leader)
    return leader_to_response(leader)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leader(
    slug: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a leader. Admin only."""
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")

    await db.delete(leader)
    await db.commit()
```

Register in `src/sieve/api/app.py`:

```python
from sieve.api.leaders.routes import router as leaders_router
# ... in create_app():
app.include_router(leaders_router)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_leaders.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/leaders/routes.py src/sieve/api/app.py tests/test_leaders.py
git commit -m "feat: add Leader CRUD API routes with admin guard"
```

---

## Task 5: Update Capture Endpoint — Optional leader_id

**Files:**
- Modify: `src/sieve/api/capture/routes.py`
- Modify: `src/sieve/api/capsules/schemas.py` (add `leader_id` to `CaptureRequest`)

**Step 1: Write failing test**

File: `tests/test_leaders.py` (append)

```python
@pytest.mark.asyncio
async def test_capture_with_leader_id(app, db_session, admin_auth_headers):
    """POST /api/capture/ with leader_id should link capsule to leader."""
    # First create a leader
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        leader_resp = await client.post(
            "/api/leaders/",
            json={"name": "Test Leader", "slug": "test-leader", "description": "Test"},
            headers=admin_auth_headers,
        )
        leader_id = leader_resp.json()["id"]

        # Capture with leader_id
        capture_resp = await client.post(
            "/api/capture/",
            json={"content": "Test content about AI", "leader_id": leader_id},
            headers=admin_auth_headers,
        )
    assert capture_resp.status_code == 201
    # Capsule should be linked to leader (pack_id == leader_id)
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_leaders.py::test_capture_with_leader_id -v`
Expected: FAIL — `leader_id` field not recognized

**Step 3: Implement**

Add `leader_id` to `CaptureRequest` in `src/sieve/api/capsules/schemas.py`:

```python
class CaptureRequest(BaseModel):
    content: str = ""
    url: str | None = None
    source_url: str | None = None
    images: list[str] = []
    leader_id: str | None = None  # Optional: link capsule to a leader
```

Update `src/sieve/api/capture/routes.py` to use `leader_id`:

After creating the capsule, if `body.leader_id` is set, validate the leader exists and set `capsule.pack_id`:

```python
# After capsule creation, before db.add:
if body.leader_id:
    result = await db.execute(select(Leader).where(Leader.id == body.leader_id))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")
    capsule.pack_id = leader.id
```

Also update the leader's `capsule_count` after commit:

```python
if body.leader_id:
    count_result = await db.execute(
        select(func.count()).where(Capsule.pack_id == body.leader_id)
    )
    leader.capsule_count = count_result.scalar() or 0
    await db.commit()
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_leaders.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/capture/routes.py src/sieve/api/capsules/schemas.py tests/test_leaders.py
git commit -m "feat: add optional leader_id to capture endpoint"
```

---

## Task 6: Leader Capsules API Endpoint

**Files:**
- Modify: `src/sieve/api/leaders/routes.py`

**Step 1: Write failing test**

```python
@pytest.mark.asyncio
async def test_get_leader_capsules(app, db_session):
    """GET /api/leaders/{slug}/capsules should return capsules linked to leader."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/leaders/karpathy/capsules")
    # Should return 404 if leader doesn't exist, or 200 with capsule list
    assert response.status_code in (200, 404)
```

**Step 2: Implement**

Add to `src/sieve/api/leaders/routes.py`:

```python
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleListResponse


@router.get("/{slug}/capsules", response_model=CapsuleListResponse)
async def get_leader_capsules(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get capsules for a leader. Public endpoint."""
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")

    query = (
        select(Capsule)
        .where(Capsule.pack_id == leader.id)
        .order_by(Capsule.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    capsules = result.scalars().all()

    count_q = select(func.count()).where(Capsule.pack_id == leader.id)
    total = (await db.execute(count_q)).scalar() or 0

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=total,
    )
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_leaders.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/sieve/api/leaders/routes.py tests/test_leaders.py
git commit -m "feat: add GET /api/leaders/{slug}/capsules endpoint"
```

---

## Task 7: HTMX Routes for Leaders

**Files:**
- Modify: `src/sieve/dashboard/htmx_routes.py`
- Create: `src/sieve/dashboard/templates/partials/leader_card.html`
- Create: `src/sieve/dashboard/templates/partials/leader_grid.html`

**Step 1: Create the leader card partial**

File: `src/sieve/dashboard/templates/partials/leader_card.html`

```html
<div class="card leader-card">
    {% if leader.avatar_url %}
    <img src="{{ leader.avatar_url }}" alt="{{ leader.name }}" class="leader-avatar">
    {% else %}
    <div class="leader-avatar leader-avatar--placeholder">{{ leader.name[0] }}</div>
    {% endif %}
    <h3 class="card-title">{{ leader.name }}</h3>
    <span class="tag-chip tag-chip--domain">{{ leader.expertise_domain }}</span>
    <p class="card-summary">{{ leader.bio or leader.description }}</p>
    <div class="leader-stats">
        <span>{{ leader.capsule_count }} capsule{{ "s" if leader.capsule_count != 1 }}</span>
    </div>
    <a href="/leader/{{ leader.slug }}" class="btn btn-secondary btn-block">View</a>
</div>
```

File: `src/sieve/dashboard/templates/partials/leader_grid.html`

```html
{% if leaders %}
    {% for leader in leaders %}
        {% include "partials/leader_card.html" %}
    {% endfor %}
{% else %}
    <div class="empty-state" style="grid-column: 1 / -1">
        <h3>No leaders found</h3>
        <p>Leader profiles will appear here once added.</p>
    </div>
{% endif %}
```

**Step 2: Add HTMX route**

Add to `src/sieve/dashboard/htmx_routes.py`:

```python
from sieve.db.models import Leader  # add to imports


@router.get("/leaders/", response_class=HTMLResponse)
async def htmx_list_leaders(
    domain: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: leader card grid with optional domain filter."""
    query = select(Leader)

    if domain:
        query = query.where(Leader.expertise_domain == domain)
    if search:
        term = f"%{escape_like(search)}%"
        query = query.where(
            or_(Leader.name.ilike(term), Leader.description.ilike(term), Leader.bio.ilike(term))
        )

    query = query.order_by(Leader.is_featured.desc(), Leader.name.asc()).limit(200)
    result = await db.execute(query)
    leaders = result.scalars().all()

    leader_dicts = []
    for l in leaders:
        leader_dicts.append({
            "id": str(l.id),
            "name": l.name,
            "slug": l.slug,
            "description": l.description,
            "bio": l.bio or "",
            "expertise_domain": l.expertise_domain or "",
            "avatar_url": l.avatar_url,
            "capsule_count": l.capsule_count,
            "is_featured": l.is_featured,
        })

    return _render_partial("partials/leader_grid.html", leaders=leader_dicts)


@router.get("/leaders/{slug}/capsules/", response_class=HTMLResponse)
async def htmx_leader_capsules(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: capsule grid for a specific leader."""
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        return HTMLResponse(content='<div class="empty-state"><h3>Leader not found</h3></div>')

    query = (
        select(Capsule)
        .where(Capsule.pack_id == leader.id)
        .order_by(Capsule.created_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    capsules = result.scalars().all()
    capsule_dicts = [capsule_to_response(c).model_dump() for c in capsules]

    return _render_partial("partials/capsule_grid.html", capsules=capsule_dicts, grouped_capsules=None, count=len(capsule_dicts))
```

**Step 3: Run tests**

Run: `uv run pytest -v`
Expected: PASS

**Step 4: Commit**

```bash
git add src/sieve/dashboard/htmx_routes.py src/sieve/dashboard/templates/partials/leader_card.html src/sieve/dashboard/templates/partials/leader_grid.html
git commit -m "feat: add HTMX routes and partials for leader grid"
```

---

## Task 8: Discover Page — Add Leaders Tab

**Files:**
- Modify: `src/sieve/dashboard/templates/discover.html`
- Modify: `src/sieve/dashboard/static/style.css` (leader card styles)

**Step 1: Update discover.html**

Replace the current discover page with a tabbed layout that includes Leaders as the first tab:

```html
{% extends "base.html" %}
{% block title %}Discover — Neural Sieve{% endblock %}
{% block content %}
<section class="page-header">
    <h1>Discover</h1>
    <p class="page-subtitle">Learn from the best minds in tech</p>
</section>

<!-- Tab bar -->
<div class="tab-bar">
    <button class="tab-btn tab-btn--active" hx-get="/htmx/leaders/" hx-target="#discover-content" hx-swap="innerHTML">Leaders</button>
    <button class="tab-btn" hx-get="/htmx/discover/sieves" hx-target="#discover-content" hx-swap="innerHTML">Sieves</button>
    <button class="tab-btn" hx-get="/htmx/discover/capsules" hx-target="#discover-content" hx-swap="innerHTML">Capsules</button>
</div>

<!-- Domain filter (for leaders tab) -->
<div id="domain-filter" class="filter-pills">
    <button class="pill pill--active" hx-get="/htmx/leaders/" hx-target="#discover-content" hx-swap="innerHTML">All</button>
    <button class="pill" hx-get="/htmx/leaders/?domain=AI/ML" hx-target="#discover-content" hx-swap="innerHTML">AI/ML</button>
    <button class="pill" hx-get="/htmx/leaders/?domain=Developer+Tools" hx-target="#discover-content" hx-swap="innerHTML">Dev Tools</button>
    <button class="pill" hx-get="/htmx/leaders/?domain=Search+%26+Retrieval" hx-target="#discover-content" hx-swap="innerHTML">Search</button>
    <button class="pill" hx-get="/htmx/leaders/?domain=Startups+%26+Indie+Hacking" hx-target="#discover-content" hx-swap="innerHTML">Startups</button>
    <button class="pill" hx-get="/htmx/leaders/?domain=Product+%26+Design" hx-target="#discover-content" hx-swap="innerHTML">Product</button>
    <button class="pill" hx-get="/htmx/leaders/?domain=Engineering+Leadership" hx-target="#discover-content" hx-swap="innerHTML">Engineering</button>
    <button class="pill" hx-get="/htmx/leaders/?domain=Open+Source" hx-target="#discover-content" hx-swap="innerHTML">Open Source</button>
</div>

<!-- Content area -->
<div id="discover-content" class="card-grid"
     hx-get="/htmx/leaders/"
     hx-trigger="load"
     hx-swap="innerHTML">
    <div style="text-align:center;padding:2rem;grid-column:1/-1"><span class="spinner spinner--lg"></span></div>
</div>
{% endblock %}
```

**Step 2: Add leader card CSS**

Add to `src/sieve/dashboard/static/style.css`:

```css
/* Leader cards */
.leader-card { text-align: center; }
.leader-avatar { width: 80px; height: 80px; border-radius: 50%; object-fit: cover; margin: 0 auto 0.75rem; display: block; }
.leader-avatar--placeholder { background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: 700; }
.leader-stats { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem; }
.tag-chip--domain { background: var(--accent); color: #fff; font-size: 0.75rem; }

/* Domain filter pills */
.filter-pills { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.pill { padding: 0.375rem 1rem; border-radius: 9999px; border: 1px solid var(--border); background: transparent; cursor: pointer; font-size: 0.85rem; color: var(--text-muted); transition: all 0.15s; }
.pill:hover, .pill--active { background: var(--accent); color: #fff; border-color: var(--accent); }

/* Tab bar */
.tab-bar { display: flex; gap: 0; border-bottom: 1px solid var(--border); margin-bottom: 1.5rem; }
.tab-btn { padding: 0.75rem 1.5rem; background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer; font-size: 0.9rem; color: var(--text-muted); transition: all 0.15s; }
.tab-btn:hover { color: var(--text); }
.tab-btn--active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
```

**Step 3: Test visually**

Run: `uv run sieve serve`
Navigate to `/discover` and verify the layout renders correctly (even with no leaders yet).

**Step 4: Commit**

```bash
git add src/sieve/dashboard/templates/discover.html src/sieve/dashboard/static/style.css
git commit -m "feat: add Leaders tab to discover page with domain filter pills"
```

---

## Task 9: Leader Profile Page

**Files:**
- Create: `src/sieve/dashboard/templates/leader.html`
- Modify: `src/sieve/dashboard/routes.py` (add `/leader/{slug}` route)

**Step 1: Create template**

File: `src/sieve/dashboard/templates/leader.html`:

```html
{% extends "base.html" %}
{% block title %}{{ leader.name }} — Neural Sieve{% endblock %}
{% block content %}
<div class="leader-profile">
    <div class="leader-header">
        {% if leader.avatar_url %}
        <img src="{{ leader.avatar_url }}" alt="{{ leader.name }}" class="leader-profile-avatar">
        {% else %}
        <div class="leader-profile-avatar leader-avatar--placeholder">{{ leader.name[0] }}</div>
        {% endif %}
        <div class="leader-info">
            <h1>{{ leader.name }}</h1>
            <span class="tag-chip tag-chip--domain">{{ leader.expertise_domain }}</span>
            <p class="leader-bio">{{ leader.bio or leader.description }}</p>
            <div class="leader-links">
                {% if leader.twitter_url %}
                <a href="{{ leader.twitter_url }}" target="_blank" rel="noopener" class="leader-link">X/Twitter</a>
                {% endif %}
                {% if leader.linkedin_url %}
                <a href="{{ leader.linkedin_url }}" target="_blank" rel="noopener" class="leader-link">LinkedIn</a>
                {% endif %}
                {% if leader.author_url %}
                <a href="{{ leader.author_url }}" target="_blank" rel="noopener" class="leader-link">Website</a>
                {% endif %}
            </div>
        </div>
    </div>
</div>

<h2 style="margin-top:2rem">Capsules ({{ leader.capsule_count }})</h2>
<div id="leader-capsules" class="card-grid"
     hx-get="/htmx/leaders/{{ leader.slug }}/capsules/"
     hx-trigger="load"
     hx-swap="innerHTML">
    {% include "partials/skeleton_grid.html" %}
</div>
{% endblock %}
```

**Step 2: Add route**

Add to `src/sieve/dashboard/routes.py`:

```python
from sieve.db.models import Leader  # add to imports


@router.get("/leader/{slug}", response_class=HTMLResponse)
async def leader_profile(request: Request, slug: str, db: AsyncSession = Depends(get_db)):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")

    leader_dict = {
        "name": leader.name,
        "slug": leader.slug,
        "description": leader.description,
        "bio": leader.bio or "",
        "expertise_domain": leader.expertise_domain or "",
        "avatar_url": leader.avatar_url,
        "twitter_url": leader.twitter_url,
        "linkedin_url": leader.linkedin_url,
        "author_url": leader.author_url,
        "capsule_count": leader.capsule_count,
    }

    return _render(request, "leader.html", {"leader": leader_dict})
```

**Step 3: Add profile CSS**

Append to `src/sieve/dashboard/static/style.css`:

```css
/* Leader profile page */
.leader-profile { margin-bottom: 1.5rem; }
.leader-header { display: flex; gap: 1.5rem; align-items: flex-start; }
.leader-profile-avatar { width: 120px; height: 120px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.leader-info h1 { margin: 0 0 0.5rem; }
.leader-bio { color: var(--text-muted); margin: 0.75rem 0; }
.leader-links { display: flex; gap: 1rem; }
.leader-link { color: var(--accent); text-decoration: none; font-size: 0.85rem; }
.leader-link:hover { text-decoration: underline; }
```

**Step 4: Test visually**

Run: `uv run sieve serve`
Navigate to `/leader/test-slug` (will 404 until leaders are seeded, but the route should work).

**Step 5: Commit**

```bash
git add src/sieve/dashboard/templates/leader.html src/sieve/dashboard/routes.py src/sieve/dashboard/static/style.css
git commit -m "feat: add leader profile page with capsule grid"
```

---

## Task 10: CLI Seed Leaders Command

**Files:**
- Modify: `src/sieve/cli.py`

**Step 1: Add the command**

Add to `src/sieve/cli.py`:

```python
@cli.command("seed-leaders")
@click.option("--file", "filepath", type=click.Path(exists=True), required=True, help="JSON file with leader data")
def seed_leaders(filepath):
    """Seed the database with leaders from a JSON file."""
    import asyncio
    import json

    with open(filepath) as f:
        leaders_data = json.load(f)

    click.echo(f"Seeding {len(leaders_data)} leaders...")
    count = asyncio.run(_seed_leaders(leaders_data))
    click.echo(f"Done. {count} leader(s) seeded.")


async def _seed_leaders(leaders_data: list[dict]) -> int:
    from slugify import slugify
    from sqlalchemy import select

    from sieve.db.database import async_session
    from sieve.db.models import Leader

    count = 0
    async with async_session() as session:
        for data in leaders_data:
            slug = data.get("slug") or slugify(data["name"])
            result = await session.execute(select(Leader).where(Leader.slug == slug))
            if result.scalar_one_or_none():
                click.echo(f"  Skipping {data['name']} (slug '{slug}' exists)")
                continue

            leader = Leader(
                name=data["name"],
                slug=slug,
                description=data.get("description", ""),
                bio=data.get("bio", ""),
                expertise_domain=data.get("expertise_domain", ""),
                avatar_url=data.get("avatar_url"),
                twitter_url=data.get("twitter_url"),
                linkedin_url=data.get("linkedin_url"),
                author_url=data.get("author_url"),
                topics=data.get("topics", []),
                is_featured=data.get("is_featured", False),
            )
            session.add(leader)
            count += 1
            click.echo(f"  Added {data['name']} ({slug})")

        await session.commit()
    return count
```

**Step 2: Create example seed file**

File: `data/leaders-seed.json`:

```json
[
  {
    "name": "Andrej Karpathy",
    "slug": "karpathy",
    "description": "AI researcher and educator. Former Director of AI at Tesla, founding member of OpenAI.",
    "bio": "Former Director of AI at Tesla, founding member of OpenAI",
    "expertise_domain": "AI/ML",
    "twitter_url": "https://x.com/karpathy",
    "author_url": "https://karpathy.ai",
    "topics": ["deep-learning", "neural-networks", "AI-education", "autonomous-driving"],
    "is_featured": true
  }
]
```

**Step 3: Test the command**

Run: `uv run sieve seed-leaders --file data/leaders-seed.json`
Expected: `Seeding 1 leaders... Added Andrej Karpathy (karpathy) Done. 1 leader(s) seeded.`

**Step 4: Commit**

```bash
git add src/sieve/cli.py data/leaders-seed.json
git commit -m "feat: add seed-leaders CLI command with example JSON"
```

---

## Task 11: Extension — Add is_admin to Auth Storage

**Files:**
- Modify: `extension/src/types/types.ts` (add `isAdmin` to auth user type)
- Modify: `extension/src/utils/sieve-api-client.ts` (return `is_admin` from `/auth/me`)
- Modify: `extension/src/utils/storage-utils.ts` (store `isAdmin`)

**Step 1: Update types**

In `extension/src/types/types.ts`, add `isAdmin` to the auth user type:

```typescript
authUser: {
    email: string;
    username: string;
    displayName: string;
    isAdmin: boolean;  // NEW
} | null;
```

**Step 2: Update API client**

In `extension/src/utils/sieve-api-client.ts`, when calling `/api/auth/me`, store the `is_admin` field from the response as `isAdmin`.

**Step 3: Update storage**

In the login flow, after fetching the current user, store `isAdmin: userData.is_admin` in the auth object.

**Step 4: Build and test**

Run: `cd extension && npm run build`
Expected: Extension compiles. Check that `isAdmin` is stored after login by inspecting `browser.storage.sync` in DevTools.

**Step 5: Commit**

```bash
git add extension/src/types/types.ts extension/src/utils/sieve-api-client.ts extension/src/utils/storage-utils.ts
git commit -m "feat: add isAdmin to extension auth storage from /auth/me response"
```

---

## Task 12: Extension — Twitter DOM Extractor

**Files:**
- Create: `extension/src/utils/twitter-extractor.ts`

**Step 1: Create the extractor**

File: `extension/src/utils/twitter-extractor.ts`:

```typescript
export interface TwitterProfile {
    name: string;
    handle: string;
    bio: string;
    avatarUrl: string | null;
    websiteUrl: string | null;
    location: string | null;
}

/**
 * Detect if the current page is a Twitter/X profile page.
 */
export function isTwitterProfile(url: string): boolean {
    const parsed = new URL(url);
    if (!['twitter.com', 'x.com'].includes(parsed.hostname)) return false;
    // Profile pages: /username (no second path segment like /status/)
    const segments = parsed.pathname.split('/').filter(Boolean);
    return segments.length === 1 && !['home', 'explore', 'search', 'notifications', 'messages', 'settings', 'i'].includes(segments[0]);
}

/**
 * Extract profile data from the current Twitter/X profile page DOM.
 * Must run as a content script on the page.
 */
export function extractTwitterProfile(): TwitterProfile | null {
    try {
        // Display name from the main heading
        const nameEl = document.querySelector('[data-testid="UserName"] span');
        const name = nameEl?.textContent?.trim() || '';

        // Handle from URL
        const handle = window.location.pathname.split('/').filter(Boolean)[0] || '';

        // Bio
        const bioEl = document.querySelector('[data-testid="UserDescription"]');
        const bio = bioEl?.textContent?.trim() || '';

        // Avatar (high-res: replace _normal or _bigger with _400x400)
        const avatarEl = document.querySelector('[data-testid="UserAvatar"] img') as HTMLImageElement;
        let avatarUrl = avatarEl?.src || null;
        if (avatarUrl) {
            avatarUrl = avatarUrl.replace(/_normal\.|_bigger\./, '_400x400.');
        }

        // Website link
        const websiteEl = document.querySelector('[data-testid="UserUrl"] a') as HTMLAnchorElement;
        const websiteUrl = websiteEl?.href || null;

        // Location
        const locationEl = document.querySelector('[data-testid="UserLocation"]');
        const location = locationEl?.textContent?.trim() || null;

        if (!name && !handle) return null;

        return { name, handle, bio, avatarUrl, websiteUrl, location };
    } catch {
        return null;
    }
}
```

**Step 2: Build and test**

Run: `cd extension && npm run build`
Expected: Compiles without errors.

**Step 3: Commit**

```bash
git add extension/src/utils/twitter-extractor.ts
git commit -m "feat: add Twitter DOM profile extractor for extension"
```

---

## Task 13: Extension — Admin Leader UI in Popup

**Files:**
- Modify: `extension/src/core/popup.ts` (add admin section)
- Modify: `extension/src/popup.html` (add admin UI elements)
- Modify: `extension/src/utils/sieve-api-client.ts` (add leader API calls)

**Step 1: Add leader API functions**

In `extension/src/utils/sieve-api-client.ts`, add:

```typescript
export async function createLeader(serverUrl: string, authToken: string, data: {
    name: string;
    slug: string;
    description: string;
    bio?: string;
    expertise_domain?: string;
    avatar_url?: string;
    twitter_url?: string;
    author_url?: string;
    topics?: string[];
}): Promise<any> {
    const response = await fetch(`${serverUrl}/api/leaders/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error(`Failed to create leader: ${response.status}`);
    return response.json();
}

export async function listLeaders(serverUrl: string, authToken: string): Promise<any[]> {
    const response = await fetch(`${serverUrl}/api/leaders/`, {
        headers: { 'Authorization': `Bearer ${authToken}` },
    });
    if (!response.ok) return [];
    const data = await response.json();
    return data.leaders || [];
}

export async function captureToLeader(serverUrl: string, authToken: string, request: {
    content: string;
    url?: string;
    leader_id: string;
}): Promise<any> {
    const response = await fetch(`${serverUrl}/api/capture/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(request),
    });
    if (!response.ok) throw new Error(`Failed to capture: ${response.status}`);
    return response.json();
}
```

**Step 2: Add admin section to popup.html**

Add a hidden admin section in `extension/src/popup.html` (inside `.clipper-footer`, before the action buttons):

```html
<div id="admin-section" style="display:none">
    <div class="admin-divider">Admin</div>
    <div id="add-leader-section" style="display:none">
        <div class="admin-field">
            <label>Domain</label>
            <select id="leader-domain">
                <option value="AI/ML">AI/ML</option>
                <option value="Developer Tools">Developer Tools</option>
                <option value="Search & Retrieval">Search & Retrieval</option>
                <option value="Startups & Indie Hacking">Startups & Indie Hacking</option>
                <option value="Product & Design">Product & Design</option>
                <option value="Engineering Leadership">Engineering Leadership</option>
                <option value="Open Source">Open Source</option>
                <option value="Security">Security</option>
                <option value="Data & Infrastructure">Data & Infrastructure</option>
            </select>
        </div>
        <button id="add-leader-btn" class="btn btn-secondary">Add as Leader</button>
    </div>
    <div id="capture-to-leader-section">
        <div class="admin-field">
            <label>Leader</label>
            <select id="leader-select">
                <option value="">— None —</option>
            </select>
        </div>
    </div>
</div>
```

**Step 3: Wire up logic in popup.ts**

In `extension/src/core/popup.ts`, after auth is loaded:

1. Check `isAdmin` from storage
2. If admin, show `#admin-section`
3. Send message to content script to check if current page is a Twitter profile
4. If Twitter profile, show `#add-leader-section` and pre-fill with extracted data
5. Fetch leader list and populate `#leader-select` dropdown
6. On "Add as Leader" click: send extracted profile to `createLeader()`
7. On main "Capture" click: if a leader is selected in `#leader-select`, include `leader_id` in the capture request

**Step 4: Build and test**

Run: `cd extension && npm run build`
Load the extension in Chrome, log in as admin, navigate to `x.com/karpathy`, check that admin section appears.

**Step 5: Commit**

```bash
git add extension/src/core/popup.ts extension/src/popup.html extension/src/utils/sieve-api-client.ts
git commit -m "feat: add admin leader management UI to extension popup"
```

---

## Task 14: Backend — Include is_admin in /auth/me Response

**Files:**
- Modify: `src/sieve/api/auth/routes.py` (add `is_admin` to the `/me` response)

**Step 1: Check current /me endpoint and update**

The `/api/auth/me` endpoint should return `is_admin` in its response so the extension knows whether to show admin features.

Find the `/me` endpoint in `src/sieve/api/auth/routes.py` and add `is_admin` to the response dict.

**Step 2: Run tests**

Run: `uv run pytest -v`
Expected: All pass.

**Step 3: Commit**

```bash
git add src/sieve/api/auth/routes.py
git commit -m "feat: include is_admin in /auth/me response for extension admin gating"
```

---

## Task 15: Full Integration Test + Visual QA

**Files:**
- Modify: `tests/test_leaders.py` (full integration tests)

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All pass.

**Step 2: Visual QA**

1. `uv run sieve serve`
2. Log in as admin
3. Seed a test leader: `uv run sieve seed-leaders --file data/leaders-seed.json`
4. Navigate to `/discover` — verify Leaders tab shows with Karpathy card
5. Click "View" on Karpathy → `/leader/karpathy` shows profile (no capsules yet)
6. Test the extension: navigate to Twitter, check admin section appears, try "Add as Leader"

**Step 3: Commit**

```bash
git add tests/test_leaders.py
git commit -m "test: add full integration tests for leaders system"
```

---

## Summary

| Task | What | Key Files |
|------|------|-----------|
| 1 | Alembic migration | `migrations/versions/004_...py` |
| 2 | Model rename + fields | `models.py`, `tests/test_leaders.py` |
| 3 | Admin guard + schemas | `auth/deps.py`, `leaders/schemas.py` |
| 4 | Leader API CRUD | `leaders/routes.py`, `app.py` |
| 5 | Capture with leader_id | `capture/routes.py`, `schemas.py` |
| 6 | Leader capsules endpoint | `leaders/routes.py` |
| 7 | HTMX routes + partials | `htmx_routes.py`, `leader_card.html`, `leader_grid.html` |
| 8 | Discover page tabs | `discover.html`, `style.css` |
| 9 | Leader profile page | `leader.html`, `routes.py` |
| 10 | CLI seed command | `cli.py`, `data/leaders-seed.json` |
| 11 | Extension is_admin | `types.ts`, `sieve-api-client.ts` |
| 12 | Twitter extractor | `twitter-extractor.ts` |
| 13 | Extension admin UI | `popup.ts`, `popup.html` |
| 14 | /auth/me is_admin | `auth/routes.py` |
| 15 | Integration test + QA | `test_leaders.py` |
