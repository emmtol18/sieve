# Social Network + Sieve Clipper + Obsidian Import — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Neural Sieve into a B2C knowledge-sharing social network with zero-friction capture via a forked Obsidian Clipper, social feed with follow/discover, and web-based Obsidian vault import.

**Architecture:** Four-phase approach. Phase 1 adds the social data layer (Follow model, sieve profiles, feed/discover API). Phase 2 redesigns the dashboard as a feed-first social experience. Phase 3 forks the Obsidian Web Clipper for zero-field capture. Phase 4 adds web-based vault import with LLM extraction.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async ORM, PostgreSQL, HTMX + Jinja2, Pydantic v2, Alembic migrations. Extension: TypeScript/Manifest V3 (forked from Obsidian Web Clipper).

**Design doc:** `docs/plans/2026-03-02-social-clipper-obsidian-design.md`

---

## Phase 1: Social DB + API

### Task 1: Add Follow model and username to User

**Files:**
- Modify: `src/sieve/db/models.py`
- Test: `tests/test_db_models.py`

**Step 1: Write the failing test**

Add to `tests/test_db_models.py`:

```python
@pytest.mark.asyncio
async def test_follow_model(db_session, test_user):
    """Follow model stores follower/followed sieve relationship."""
    from sieve.db.models import Follow, Sieve, User

    # Create a second user + sieve to follow
    user2 = User(email="other@example.com", display_name="Other", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    sieve2 = Sieve(user_id=user2.id, name="Other's Sieve")
    db_session.add(sieve2)
    await db_session.flush()

    user, sieve = test_user
    follow = Follow(follower_sieve_id=sieve.id, followed_sieve_id=sieve2.id)
    db_session.add(follow)
    await db_session.commit()

    assert follow.id is not None
    assert follow.follower_sieve_id == sieve.id
    assert follow.followed_sieve_id == sieve2.id
    assert follow.created_at is not None


@pytest.mark.asyncio
async def test_user_has_username(db_session, test_user):
    """User model has a username field."""
    user, _ = test_user
    assert hasattr(user, "username")


@pytest.mark.asyncio
async def test_sieve_has_bio_and_avatar(db_session, test_user):
    """Sieve model has bio and avatar_url fields."""
    _, sieve = test_user
    assert hasattr(sieve, "bio")
    assert hasattr(sieve, "avatar_url")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db_models.py::test_follow_model tests/test_db_models.py::test_user_has_username tests/test_db_models.py::test_sieve_has_bio_and_avatar -v`
Expected: FAIL — `Follow` not defined, `username`/`bio`/`avatar_url` not on models

**Step 3: Write minimal implementation**

In `src/sieve/db/models.py`, add the Follow model after the Capsule class and update User and Sieve:

Add to **User** model:
```python
username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
```

Add to **Sieve** model:
```python
bio: Mapped[str] = mapped_column(String(500), default="")
avatar_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
```

Add new **Follow** model:
```python
class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_sieve_id", "followed_sieve_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    follower_sieve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sieves.id", ondelete="CASCADE"),
        nullable=False,
    )
    followed_sieve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sieves.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

Add relationships on **Sieve**:
```python
followers: Mapped[list["Follow"]] = relationship(
    foreign_keys="Follow.followed_sieve_id",
    cascade="all, delete-orphan",
)
following: Mapped[list["Follow"]] = relationship(
    foreign_keys="Follow.follower_sieve_id",
    cascade="all, delete-orphan",
)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_db_models.py -v`
Expected: PASS

**Step 5: Update test fixtures**

The `test_user` fixture in `tests/conftest.py` creates a User. Update it to include a `username` field:

```python
user = User(
    email="test@example.com",
    password_hash=hash_password("testpass"),
    display_name="Test User",
    username="testuser",
)
```

Also update `tests/conftest.py` anywhere else Users are created (e.g. signup tests may need a username).

**Step 6: Run full test suite**

Run: `uv run pytest -v`
Expected: PASS (fix any other tests broken by the new required `username` field)

**Step 7: Commit**

```bash
git add src/sieve/db/models.py tests/test_db_models.py tests/conftest.py
git commit -m "feat: add Follow model, username on User, bio/avatar on Sieve"
```

---

### Task 2: Alembic migration for new fields + Follow table

**Files:**
- Create: `src/sieve/db/migrations/versions/002_add_follows_and_social_fields.py`

**Step 1: Generate migration**

Run: `uv run alembic revision -m "add_follows_and_social_fields" --rev-id 002`

**Step 2: Write migration**

```python
"""add_follows_and_social_fields

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"


def upgrade() -> None:
    # Add username to users
    op.add_column("users", sa.Column("username", sa.String(50), nullable=True))
    op.create_unique_constraint("uq_users_username", "users", ["username"])

    # Add bio and avatar_url to sieves
    op.add_column("sieves", sa.Column("bio", sa.String(500), server_default=""))
    op.add_column("sieves", sa.Column("avatar_url", sa.String(2000), nullable=True))

    # Create follows table
    op.create_table(
        "follows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("follower_sieve_id", UUID(as_uuid=True), sa.ForeignKey("sieves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("followed_sieve_id", UUID(as_uuid=True), sa.ForeignKey("sieves.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("follower_sieve_id", "followed_sieve_id"),
    )


def downgrade() -> None:
    op.drop_table("follows")
    op.drop_column("sieves", "avatar_url")
    op.drop_column("sieves", "bio")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "username")
```

**Step 3: Run migration (local dev)**

Run: `uv run alembic upgrade head`
Expected: Migration applies successfully

**Step 4: Commit**

```bash
git add src/sieve/db/migrations/versions/002_add_follows_and_social_fields.py
git commit -m "migration: add follows table, username, bio, avatar_url"
```

---

### Task 3: Update auth signup to require username

**Files:**
- Modify: `src/sieve/api/auth/schemas.py`
- Modify: `src/sieve/api/auth/routes.py`
- Modify: `src/sieve/dashboard/htmx_routes.py`
- Modify: `src/sieve/dashboard/templates/login.html`
- Test: `tests/test_auth.py` (or wherever signup is tested)

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_signup_requires_username(client):
    """Signup creates user with username."""
    resp = await client.post("/api/auth/signup", json={
        "email": "new@test.com",
        "password": "secret123",
        "display_name": "New User",
        "username": "newuser",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_signup_duplicate_username_rejected(client, test_user):
    """Duplicate username returns 409."""
    resp = await client.post("/api/auth/signup", json={
        "email": "another@test.com",
        "password": "secret123",
        "display_name": "Another",
        "username": "testuser",  # same as test_user
    })
    assert resp.status_code == 409
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_auth.py::test_signup_requires_username tests/test_auth.py::test_signup_duplicate_username_rejected -v`
Expected: FAIL

**Step 3: Implement**

In `src/sieve/api/auth/schemas.py`, add `username: str` to `SignupRequest`.

In `src/sieve/api/auth/routes.py` signup endpoint:
- Check username uniqueness (query by username, return 409 if exists)
- Set `user.username = body.username`

In `src/sieve/dashboard/htmx_routes.py` HTMX signup:
- Read `username` from form data
- Same uniqueness check

In `src/sieve/dashboard/templates/login.html`:
- Add username input field to signup form (before email)

**Step 4: Run tests**

Run: `uv run pytest -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/auth/ src/sieve/dashboard/htmx_routes.py src/sieve/dashboard/templates/login.html tests/
git commit -m "feat: require username on signup, validate uniqueness"
```

---

### Task 4: Sieve profile API endpoints

**Files:**
- Create: `src/sieve/api/sieves/__init__.py`
- Create: `src/sieve/api/sieves/routes.py`
- Create: `src/sieve/api/sieves/schemas.py`
- Modify: `src/sieve/api/app.py` (register router)
- Test: `tests/test_sieves_api.py`

**Step 1: Write the failing test**

Create `tests/test_sieves_api.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_get_public_sieve_by_username(client, test_user):
    """GET /api/sieves/@username returns public sieve profile."""
    from sieve.db.models import Sieve
    # Make sieve public first
    _, sieve = test_user
    sieve.is_public = True

    resp = await client.get("/api/sieves/@testuser")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == sieve.name
    assert "capsule_count" in data
    assert "follower_count" in data
    assert "following_count" in data


@pytest.mark.asyncio
async def test_get_private_sieve_returns_404(client, test_user):
    """Private sieve is not accessible by username."""
    resp = await client.get("/api/sieves/@testuser")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_own_sieve_profile(client, auth_cookies, test_user):
    """GET /api/sieves/me returns own sieve regardless of public status."""
    resp = await client.get("/api/sieves/me", cookies=auth_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_public"] is False  # default


@pytest.mark.asyncio
async def test_update_sieve_profile(client, auth_cookies, test_user):
    """PUT /api/sieves/me updates bio and public status."""
    resp = await client.put("/api/sieves/me", cookies=auth_cookies, json={
        "bio": "Knowledge curator",
        "is_public": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["bio"] == "Knowledge curator"
    assert data["is_public"] is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sieves_api.py -v`
Expected: FAIL — 404, routes don't exist

**Step 3: Create schemas**

Create `src/sieve/api/sieves/schemas.py`:

```python
from pydantic import BaseModel


class SieveProfileResponse(BaseModel):
    id: str
    name: str
    username: str
    display_name: str
    bio: str
    avatar_url: str | None
    is_public: bool
    capsule_count: int
    follower_count: int
    following_count: int
    created_at: str


class SieveUpdateRequest(BaseModel):
    name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    is_public: bool | None = None
```

**Step 4: Create routes**

Create `src/sieve/api/sieves/__init__.py` (empty).

Create `src/sieve/api/sieves/routes.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.api.sieves.schemas import SieveProfileResponse, SieveUpdateRequest
from sieve.db.database import get_db
from sieve.db.models import Capsule, Follow, Sieve, User

router = APIRouter(prefix="/api/sieves", tags=["sieves"])


def _sieve_to_profile(sieve: Sieve, user: User, capsule_count: int, follower_count: int, following_count: int) -> SieveProfileResponse:
    return SieveProfileResponse(
        id=str(sieve.id),
        name=sieve.name,
        username=user.username,
        display_name=user.display_name,
        bio=sieve.bio or "",
        avatar_url=sieve.avatar_url,
        is_public=sieve.is_public,
        capsule_count=capsule_count,
        follower_count=follower_count,
        following_count=following_count,
        created_at=sieve.created_at.isoformat(),
    )


async def _get_sieve_counts(db: AsyncSession, sieve_id: uuid.UUID) -> tuple[int, int, int]:
    capsule_q = select(func.count()).select_from(Capsule).where(Capsule.sieve_id == sieve_id, Capsule.status == "active")
    follower_q = select(func.count()).select_from(Follow).where(Follow.followed_sieve_id == sieve_id)
    following_q = select(func.count()).select_from(Follow).where(Follow.follower_sieve_id == sieve_id)
    capsule_count = (await db.execute(capsule_q)).scalar() or 0
    follower_count = (await db.execute(follower_q)).scalar() or 0
    following_count = (await db.execute(following_q)).scalar() or 0
    return capsule_count, follower_count, following_count


@router.get("/me", response_model=SieveProfileResponse)
async def get_own_sieve(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sieve = (await db.execute(select(Sieve).where(Sieve.user_id == user.id))).scalar_one_or_none()
    if not sieve:
        raise HTTPException(404, "Sieve not found")
    counts = await _get_sieve_counts(db, sieve.id)
    return _sieve_to_profile(sieve, user, *counts)


@router.put("/me", response_model=SieveProfileResponse)
async def update_own_sieve(body: SieveUpdateRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sieve = (await db.execute(select(Sieve).where(Sieve.user_id == user.id))).scalar_one_or_none()
    if not sieve:
        raise HTTPException(404, "Sieve not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sieve, field, value)
    await db.commit()
    await db.refresh(sieve)
    counts = await _get_sieve_counts(db, sieve.id)
    return _sieve_to_profile(sieve, user, *counts)


@router.get("/@{username}", response_model=SieveProfileResponse)
async def get_sieve_by_username(username: str, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    sieve = (await db.execute(select(Sieve).where(Sieve.user_id == user.id))).scalar_one_or_none()
    if not sieve or not sieve.is_public:
        raise HTTPException(404, "Sieve not found")
    counts = await _get_sieve_counts(db, sieve.id)
    return _sieve_to_profile(sieve, user, *counts)
```

**Step 5: Register router in app.py**

In `src/sieve/api/app.py`, add:
```python
from sieve.api.sieves.routes import router as sieves_router
# ...
app.include_router(sieves_router)
```

**Step 6: Run tests**

Run: `uv run pytest tests/test_sieves_api.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/sieve/api/sieves/ src/sieve/api/app.py tests/test_sieves_api.py
git commit -m "feat: add sieve profile API (get by username, own profile, update)"
```

---

### Task 5: Follow / Unfollow API endpoints

**Files:**
- Modify: `src/sieve/api/sieves/routes.py`
- Test: `tests/test_sieves_api.py`

**Step 1: Write the failing test**

Add to `tests/test_sieves_api.py`:

```python
@pytest.mark.asyncio
async def test_follow_sieve(client, auth_cookies, db_session, test_user):
    """POST /api/sieves/@username/follow creates a follow."""
    from sieve.db.models import Sieve, User

    user2 = User(email="leader@test.com", display_name="Leader", username="leader", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    sieve2 = Sieve(user_id=user2.id, name="Leader's Sieve", is_public=True)
    db_session.add(sieve2)
    await db_session.commit()

    resp = await client.post("/api/sieves/@leader/follow", cookies=auth_cookies)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_unfollow_sieve(client, auth_cookies, db_session, test_user):
    """DELETE /api/sieves/@username/follow removes the follow."""
    from sieve.db.models import Follow, Sieve, User

    user2 = User(email="leader2@test.com", display_name="Leader2", username="leader2", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    sieve2 = Sieve(user_id=user2.id, name="Leader2's Sieve", is_public=True)
    db_session.add(sieve2)
    await db_session.flush()

    _, my_sieve = test_user
    follow = Follow(follower_sieve_id=my_sieve.id, followed_sieve_id=sieve2.id)
    db_session.add(follow)
    await db_session.commit()

    resp = await client.delete("/api/sieves/@leader2/follow", cookies=auth_cookies)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_cannot_follow_self(client, auth_cookies, test_user):
    """Cannot follow own sieve."""
    _, sieve = test_user
    sieve.is_public = True
    resp = await client.post("/api/sieves/@testuser/follow", cookies=auth_cookies)
    assert resp.status_code == 400
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_sieves_api.py::test_follow_sieve tests/test_sieves_api.py::test_unfollow_sieve tests/test_sieves_api.py::test_cannot_follow_self -v`
Expected: FAIL — 404/405

**Step 3: Implement follow/unfollow**

Add to `src/sieve/api/sieves/routes.py`:

```python
@router.post("/@{username}/follow", status_code=201)
async def follow_sieve(username: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not target_user:
        raise HTTPException(404, "User not found")
    target_sieve = (await db.execute(select(Sieve).where(Sieve.user_id == target_user.id))).scalar_one_or_none()
    if not target_sieve or not target_sieve.is_public:
        raise HTTPException(404, "Sieve not found")

    my_sieve = (await db.execute(select(Sieve).where(Sieve.user_id == user.id))).scalar_one_or_none()
    if not my_sieve:
        raise HTTPException(404, "Your sieve not found")
    if my_sieve.id == target_sieve.id:
        raise HTTPException(400, "Cannot follow yourself")

    existing = (await db.execute(
        select(Follow).where(Follow.follower_sieve_id == my_sieve.id, Follow.followed_sieve_id == target_sieve.id)
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Already following")

    follow = Follow(follower_sieve_id=my_sieve.id, followed_sieve_id=target_sieve.id)
    db.add(follow)
    await db.commit()
    return {"status": "following"}


@router.delete("/@{username}/follow", status_code=204)
async def unfollow_sieve(username: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    target_user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not target_user:
        raise HTTPException(404, "User not found")
    target_sieve = (await db.execute(select(Sieve).where(Sieve.user_id == target_user.id))).scalar_one_or_none()
    if not target_sieve:
        raise HTTPException(404, "Sieve not found")

    my_sieve = (await db.execute(select(Sieve).where(Sieve.user_id == user.id))).scalar_one_or_none()
    if not my_sieve:
        raise HTTPException(404, "Your sieve not found")

    follow = (await db.execute(
        select(Follow).where(Follow.follower_sieve_id == my_sieve.id, Follow.followed_sieve_id == target_sieve.id)
    )).scalar_one_or_none()
    if not follow:
        raise HTTPException(404, "Not following")

    await db.delete(follow)
    await db.commit()
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_sieves_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/sieves/routes.py tests/test_sieves_api.py
git commit -m "feat: add follow/unfollow API endpoints"
```

---

### Task 6: Feed API endpoint

**Files:**
- Create: `src/sieve/api/feed/__init__.py`
- Create: `src/sieve/api/feed/routes.py`
- Modify: `src/sieve/api/app.py`
- Test: `tests/test_feed_api.py`

**Step 1: Write the failing test**

Create `tests/test_feed_api.py`:

```python
import pytest

from sieve.db.models import Capsule, Follow, Sieve, User


@pytest.mark.asyncio
async def test_feed_shows_own_capsules(client, auth_cookies, db_session, test_user):
    """Feed includes user's own capsules."""
    _, sieve = test_user
    capsule = Capsule(
        sieve_id=sieve.id, title="My Note", executive_summary="summary",
        core_insight="insight", full_content="content",
    )
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/feed/", cookies=auth_cookies)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(c["title"] == "My Note" for c in data["capsules"])


@pytest.mark.asyncio
async def test_feed_shows_followed_capsules(client, auth_cookies, db_session, test_user):
    """Feed includes capsules from followed public sieves."""
    _, my_sieve = test_user

    user2 = User(email="feed@test.com", display_name="Feed", username="feeduser", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    sieve2 = Sieve(user_id=user2.id, name="Feed Sieve", is_public=True)
    db_session.add(sieve2)
    await db_session.flush()

    follow = Follow(follower_sieve_id=my_sieve.id, followed_sieve_id=sieve2.id)
    db_session.add(follow)
    capsule = Capsule(
        sieve_id=sieve2.id, title="Followed Note", executive_summary="s",
        core_insight="i", full_content="c",
    )
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/feed/", cookies=auth_cookies)
    data = resp.json()
    assert any(c["title"] == "Followed Note" for c in data["capsules"])


@pytest.mark.asyncio
async def test_feed_excludes_unfollowed(client, auth_cookies, db_session, test_user):
    """Feed does not include capsules from sieves not followed."""
    user2 = User(email="stranger@test.com", display_name="Stranger", username="stranger", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    sieve2 = Sieve(user_id=user2.id, name="Stranger Sieve", is_public=True)
    db_session.add(sieve2)
    await db_session.flush()
    capsule = Capsule(
        sieve_id=sieve2.id, title="Stranger Note", executive_summary="s",
        core_insight="i", full_content="c",
    )
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/feed/", cookies=auth_cookies)
    data = resp.json()
    assert not any(c["title"] == "Stranger Note" for c in data["capsules"])
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_feed_api.py -v`
Expected: FAIL — 404

**Step 3: Implement**

Create `src/sieve/api/feed/__init__.py` (empty).

Create `src/sieve/api/feed/routes.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleListResponse
from sieve.db.database import get_db
from sieve.db.models import Capsule, Follow, Sieve, User

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("/", response_model=CapsuleListResponse)
async def get_feed(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    my_sieve = (await db.execute(select(Sieve).where(Sieve.user_id == user.id))).scalar_one_or_none()
    if not my_sieve:
        return CapsuleListResponse(capsules=[], total=0)

    # Get IDs of sieves I follow
    followed_ids_q = select(Follow.followed_sieve_id).where(Follow.follower_sieve_id == my_sieve.id)
    followed_ids = (await db.execute(followed_ids_q)).scalars().all()

    # Feed = my capsules + followed sieves' capsules
    sieve_ids = [my_sieve.id] + list(followed_ids)
    base_q = select(Capsule).where(Capsule.sieve_id.in_(sieve_ids), Capsule.status == "active")

    total = (await db.execute(select(func.count()).select_from(base_q.subquery()))).scalar() or 0
    capsules = (await db.execute(base_q.order_by(Capsule.created_at.desc()).offset(offset).limit(limit))).scalars().all()

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=total,
    )
```

Add missing import at top: `from sqlalchemy import func, or_, select`

Register in `src/sieve/api/app.py`:
```python
from sieve.api.feed.routes import router as feed_router
# ...
app.include_router(feed_router)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_feed_api.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/feed/ src/sieve/api/app.py tests/test_feed_api.py
git commit -m "feat: add feed API endpoint (own + followed capsules)"
```

---

### Task 7: Discover API endpoint

**Files:**
- Create: `src/sieve/api/discover/__init__.py`
- Create: `src/sieve/api/discover/routes.py`
- Modify: `src/sieve/api/app.py`
- Test: `tests/test_discover_api.py`

**Step 1: Write the failing test**

Create `tests/test_discover_api.py`:

```python
import pytest

from sieve.db.models import Capsule, Sieve, User


@pytest.mark.asyncio
async def test_discover_returns_public_sieves(client, db_session):
    """GET /api/discover/sieves returns public sieves only."""
    user = User(email="pub@test.com", display_name="Public", username="pubuser", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    sieve = Sieve(user_id=user.id, name="Public Sieve", is_public=True, bio="Great content")
    db_session.add(sieve)

    user2 = User(email="priv@test.com", display_name="Private", username="privuser", password_hash="x")
    db_session.add(user2)
    await db_session.flush()
    sieve2 = Sieve(user_id=user2.id, name="Private Sieve", is_public=False)
    db_session.add(sieve2)
    await db_session.commit()

    resp = await client.get("/api/discover/sieves")
    assert resp.status_code == 200
    data = resp.json()
    names = [s["name"] for s in data["sieves"]]
    assert "Public Sieve" in names
    assert "Private Sieve" not in names


@pytest.mark.asyncio
async def test_discover_search_by_tag(client, db_session):
    """GET /api/discover/capsules?tag=ai returns public capsules with that tag."""
    user = User(email="tag@test.com", display_name="Tagger", username="tagger", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    sieve = Sieve(user_id=user.id, name="Tag Sieve", is_public=True)
    db_session.add(sieve)
    await db_session.flush()
    capsule = Capsule(
        sieve_id=sieve.id, title="AI Note", executive_summary="s",
        core_insight="i", full_content="c", tags=["ai", "ml"],
    )
    db_session.add(capsule)
    await db_session.commit()

    resp = await client.get("/api/discover/capsules?tag=ai")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_discover_api.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/sieve/api/discover/__init__.py` (empty).

Create `src/sieve/api/discover/routes.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleListResponse
from sieve.api.sieves.schemas import SieveProfileResponse
from sieve.api.sieves.routes import _get_sieve_counts, _sieve_to_profile
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, User

router = APIRouter(prefix="/api/discover", tags=["discover"])


@router.get("/sieves")
async def discover_sieves(
    search: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Sieve, User).join(User, Sieve.user_id == User.id).where(Sieve.is_public == True)
    if search:
        q = q.where(Sieve.name.ilike(f"%{search}%") | User.display_name.ilike(f"%{search}%"))
    q = q.order_by(Sieve.created_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(q)).all()

    sieves = []
    for sieve, user in rows:
        counts = await _get_sieve_counts(db, sieve.id)
        sieves.append(_sieve_to_profile(sieve, user, *counts))
    return {"sieves": sieves, "total": len(sieves)}


@router.get("/capsules", response_model=CapsuleListResponse)
async def discover_capsules(
    tag: str = Query(default="", max_length=100),
    category: str = Query(default="", max_length=200),
    search: str = Query(default="", max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    # Only capsules from public sieves
    public_sieve_ids = select(Sieve.id).where(Sieve.is_public == True)
    q = select(Capsule).where(Capsule.sieve_id.in_(public_sieve_ids), Capsule.status == "active")

    if tag:
        q = q.where(Capsule.tags.any(tag))
    if category:
        q = q.where(Capsule.category.ilike(f"%{category}%"))
    if search:
        q = q.where(Capsule.title.ilike(f"%{search}%") | Capsule.core_insight.ilike(f"%{search}%"))

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    capsules = (await db.execute(q.order_by(Capsule.created_at.desc()).offset(offset).limit(limit))).scalars().all()
    return CapsuleListResponse(capsules=[capsule_to_response(c) for c in capsules], total=total)
```

Register in `src/sieve/api/app.py`:
```python
from sieve.api.discover.routes import router as discover_router
app.include_router(discover_router)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_discover_api.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/sieve/api/discover/ src/sieve/api/app.py tests/test_discover_api.py
git commit -m "feat: add discover API (browse public sieves and capsules)"
```

---

## Phase 2: Feed Dashboard

### Task 8: Redesign base template with new navigation

**Files:**
- Modify: `src/sieve/dashboard/templates/base.html`
- Modify: `src/sieve/dashboard/static/style.css`
- Test: `tests/test_dashboard.py`

**Step 1: Write the failing test**

Add to `tests/test_dashboard.py`:

```python
def test_base_template_has_feed_nav():
    """Base template includes feed, discover, capture, profile navigation."""
    with open("src/sieve/dashboard/templates/base.html") as f:
        content = f.read()
    assert 'href="/"' in content or 'href="/feed"' in content  # Feed link
    assert 'href="/discover"' in content
    assert 'href="/capture"' in content
    assert 'href="/profile"' in content or 'href="/settings"' in content


def test_css_has_bottom_nav():
    """CSS includes bottom navigation for mobile."""
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".bottom-nav" in content
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard.py::test_base_template_has_feed_nav tests/test_dashboard.py::test_css_has_bottom_nav -v`
Expected: FAIL

**Step 3: Implement**

Update `src/sieve/dashboard/templates/base.html`:
- Replace current nav links with: Feed (`/`), Discover (`/discover`), Capture (`/capture`), Profile (`/settings`)
- Add bottom nav bar for mobile (`.bottom-nav`) with same links
- Keep hamburger menu for desktop side nav

Update `src/sieve/dashboard/static/style.css`:
- Add `.bottom-nav` styles: fixed bottom, 4 equal columns, icon + label
- Hide bottom nav on desktop (`@media (min-width: 768px)`)
- Show side nav on desktop, hide on mobile

**Step 4: Run tests**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/dashboard/templates/base.html src/sieve/dashboard/static/style.css tests/test_dashboard.py
git commit -m "feat: redesign nav with feed-first layout and mobile bottom nav"
```

---

### Task 9: Create feed home page

**Files:**
- Create: `src/sieve/dashboard/templates/feed.html`
- Create: `src/sieve/dashboard/templates/partials/feed_card.html`
- Modify: `src/sieve/dashboard/routes.py` (change `/` to render feed)
- Modify: `src/sieve/dashboard/htmx_routes.py` (add feed HTMX endpoint)
- Modify: `src/sieve/dashboard/static/style.css`
- Test: `tests/test_dashboard.py`

**Step 1: Write the failing test**

```python
def test_feed_template_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/feed.html")

def test_feed_card_partial_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/partials/feed_card.html")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard.py::test_feed_template_exists tests/test_dashboard.py::test_feed_card_partial_exists -v`
Expected: FAIL

**Step 3: Create feed template**

Create `src/sieve/dashboard/templates/feed.html` extending `base.html`:
- Quick capture bar at top (URL paste + text input, `hx-post="/htmx/capture/"`)
- Filter tabs: All | My Capsules | Following (switch via `hx-get` with filter param)
- Feed container: `hx-get="/htmx/feed/"`, `hx-trigger="load"`, `hx-swap="innerHTML"`
- Infinite scroll: `hx-trigger="revealed"` on sentinel element at bottom

Create `src/sieve/dashboard/templates/partials/feed_card.html`:
- Title (links to `/capsule/{id}`)
- Core insight text
- Tags (clickable, link to `/discover?tag=X`)
- Source favicon + domain (from `source_url`)
- Author sieve link (`/sieve/@username`) with display name — only if from followed sieve
- Relative timestamp ("2h ago")

**Step 4: Update routes**

In `src/sieve/dashboard/routes.py`:
- Change `GET /` to render `feed.html` (protected)
- Keep `GET /sieve` as "My Sieve" page

In `src/sieve/dashboard/htmx_routes.py`:
- Add `GET /htmx/feed/` — queries feed API logic inline, returns rendered feed cards
- Params: `filter` (all/mine/following), `offset`, `limit`

**Step 5: Add feed styles to CSS**

Add to `src/sieve/dashboard/static/style.css`:
- `.feed-card` — card with left border accent, padding
- `.feed-card .source` — small text, favicon
- `.feed-card .author` — linked username
- `.feed-card .tags` — inline tag pills
- `.feed-card .timestamp` — muted, small
- `.quick-capture` — input bar at top of feed
- `.feed-filters` — tab bar (All | Mine | Following)

**Step 6: Run tests**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add src/sieve/dashboard/templates/ src/sieve/dashboard/routes.py src/sieve/dashboard/htmx_routes.py src/sieve/dashboard/static/style.css tests/test_dashboard.py
git commit -m "feat: add feed home page with quick capture bar and infinite scroll"
```

---

### Task 10: Create discover page

**Files:**
- Create: `src/sieve/dashboard/templates/discover.html`
- Create: `src/sieve/dashboard/templates/partials/sieve_card.html`
- Modify: `src/sieve/dashboard/htmx_routes.py`
- Modify: `src/sieve/dashboard/static/style.css`
- Test: `tests/test_dashboard.py`

**Step 1: Write the failing test**

```python
def test_discover_template_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/discover.html")

def test_sieve_card_partial_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/partials/sieve_card.html")
```

**Step 2: Run test to verify fails, then implement**

Create `src/sieve/dashboard/templates/discover.html`:
- Search bar: `hx-get="/htmx/discover/sieves"`, debounced
- Category filter tabs (from existing categories)
- Two sections: "Public Sieves" grid + "Trending Capsules" feed
- HTMX-loaded content

Create `src/sieve/dashboard/templates/partials/sieve_card.html`:
- Display name, username, bio preview
- Capsule count, follower count
- Follow button: `hx-post="/htmx/sieves/@{username}/follow"`, `hx-swap="outerHTML"`
- Tags they specialize in

Add HTMX routes in `src/sieve/dashboard/htmx_routes.py`:
- `GET /htmx/discover/sieves` — renders sieve grid partial
- `GET /htmx/discover/capsules` — renders capsule feed partial

**Step 3: Run tests, commit**

Run: `uv run pytest -v`

```bash
git add src/sieve/dashboard/ tests/test_dashboard.py
git commit -m "feat: add discover page with public sieve browsing"
```

---

### Task 11: Create sieve profile page

**Files:**
- Create: `src/sieve/dashboard/templates/profile.html`
- Modify: `src/sieve/dashboard/routes.py`
- Modify: `src/sieve/dashboard/htmx_routes.py`
- Modify: `src/sieve/dashboard/static/style.css`
- Test: `tests/test_dashboard.py`

**Step 1: Write test, then implement**

Create `src/sieve/dashboard/templates/profile.html`:
- Profile header: avatar, display name, @username, bio
- Stats: capsule count, followers, following
- Follow/Unfollow button (HTMX): `hx-post` / `hx-delete` to `/htmx/sieves/@{username}/follow`
- Capsule grid below (reuse capsule_card partial)

Add route in `src/sieve/dashboard/routes.py`:
- `GET /sieve/@{username}` → renders `profile.html` (public, no auth required)

Add HTMX route:
- `POST /htmx/sieves/@{username}/follow` — creates follow, returns updated button
- `DELETE /htmx/sieves/@{username}/follow` — removes follow, returns updated button

```bash
git add src/sieve/dashboard/ tests/test_dashboard.py
git commit -m "feat: add public sieve profile page with follow/unfollow"
```

---

### Task 12: Settings page

**Files:**
- Create: `src/sieve/dashboard/templates/settings.html`
- Modify: `src/sieve/dashboard/routes.py`
- Modify: `src/sieve/dashboard/htmx_routes.py`

**Step 1: Implement**

Create `src/sieve/dashboard/templates/settings.html`:
- Profile section: edit display_name, bio, avatar_url
- Privacy: toggle is_public
- API key display (readonly, copy button)
- Obsidian sync toggle (placeholder — disabled, "Coming soon")
- Save button: `hx-put="/htmx/sieves/me"`

Add route: `GET /settings` → renders `settings.html` (protected)

Add HTMX: `PUT /htmx/sieves/me` — updates sieve profile fields

```bash
git add src/sieve/dashboard/ tests/
git commit -m "feat: add settings page with profile editing"
```

---

## Phase 3: Sieve Clipper (Browser Extension)

### Task 13: Fork and set up Obsidian Web Clipper

**Files:**
- Create: `extension/` directory (at project root)

**Step 1: Clone Obsidian Web Clipper**

The Obsidian Web Clipper is at `https://github.com/obsidianmd/obsidian-clipper`. It's MIT licensed.

```bash
# In a temporary directory, clone and copy into our project
git clone --depth 1 https://github.com/obsidianmd/obsidian-clipper /tmp/obsidian-clipper
cp -r /tmp/obsidian-clipper/src extension/src
cp /tmp/obsidian-clipper/package.json extension/package.json
cp /tmp/obsidian-clipper/tsconfig.json extension/tsconfig.json
cp /tmp/obsidian-clipper/LICENSE extension/LICENSE-obsidian-clipper
```

**Step 2: Update package.json**

Change name to `sieve-clipper`, description to "Zero-friction knowledge capture for Neural Sieve".

**Step 3: Commit the fork as-is**

```bash
git add extension/
git commit -m "chore: fork Obsidian Web Clipper (MIT) as extension base"
```

---

### Task 14: Rebrand Sieve Clipper

**Files:**
- Modify: `extension/` (icons, manifest, strings)

**Step 1: Update manifest.json**

- Change `name` to "Sieve Clipper"
- Change `description` to "Capture knowledge to your Neural Sieve. One click, zero fields."
- Update icon paths
- Keep all permissions (activeTab, storage, contextMenus)

**Step 2: Replace icons**

Create new icons in `extension/icons/` — Neural Sieve branding (16, 32, 48, 128px).

**Step 3: Update user-facing strings**

Search and replace "Obsidian" → "Sieve" in UI-facing strings (popup, overlay, settings).

**Step 4: Commit**

```bash
git add extension/
git commit -m "chore: rebrand extension as Sieve Clipper"
```

---

### Task 15: Rewire capture to Neural Sieve API

**Files:**
- Modify: Extension source files that handle saving/sending content

**Step 1: Replace Obsidian protocol handler**

The Obsidian Clipper uses `obsidian://` protocol URLs to send content to the Obsidian app. Replace this with an HTTP POST to the Neural Sieve API.

Key changes:
- Remove `obsidian://` URL construction
- Add `fetch()` call to `${apiUrl}/api/capture/` with Bearer token auth
- Store API URL and JWT in `chrome.storage.sync`
- Request body: `{ content: markdownContent, url: pageUrl }`

**Step 2: Add auth flow in popup**

Replace the Obsidian vault selector in the popup with:
- Login form (email + password) → calls `/api/auth/login` → stores JWT
- Or "Login with Google" button → opens OAuth flow in new tab
- Show logged-in state with username

**Step 3: Add one-click capture**

- Extension icon click = immediate capture (no popup/overlay needed by default)
- Background script handles: grab page content → markdown convert → POST to API
- Show browser notification on success: "Captured: [title from API response]"

**Step 4: Keep overlay as optional**

- Right-click context menu → "Capture selection to Sieve" → uses selection
- Toolbar long-press or option → opens overlay for template/selection mode
- This preserves Obsidian Clipper's power features for power users

**Step 5: Build and test locally**

```bash
cd extension && npm install && npm run build
```

Load unpacked extension in Chrome, test capture flow against local server (`http://localhost:8421`).

**Step 6: Commit**

```bash
git add extension/
git commit -m "feat: rewire Sieve Clipper to capture via Neural Sieve API"
```

---

### Task 16: Toast notifications and polish

**Files:**
- Modify: Extension source

**Step 1: Add toast notification**

After successful capture, inject a small toast element into the current page:
- Position: fixed, bottom-right
- Content: "Saved to your Sieve" + capsule title
- Auto-dismiss after 3 seconds
- Link to view capsule in dashboard

**Step 2: Add error handling**

- Network error → toast "Capture failed — check your connection"
- Auth error (401) → toast "Please log in to Sieve Clipper"
- Show extension badge with "!" on error

**Step 3: Commit**

```bash
git add extension/
git commit -m "feat: add toast notifications and error handling to Sieve Clipper"
```

---

## Phase 4: Obsidian Vault Import

### Task 17: Markdown parser for Obsidian notes

**Files:**
- Create: `src/sieve/import/__init__.py`
- Create: `src/sieve/import/parser.py`
- Test: `tests/test_import_parser.py`

**Step 1: Write the failing test**

Create `tests/test_import_parser.py`:

```python
import pytest

from sieve.import_vault.parser import parse_obsidian_note


def test_parse_note_with_frontmatter():
    """Parses YAML frontmatter and markdown body."""
    content = """---
tags:
  - ai
  - machine-learning
aliases:
  - ML Basics
created: 2025-06-15
---

# Machine Learning Fundamentals

Key concepts in ML include supervised and unsupervised learning.
"""
    result = parse_obsidian_note(content, "ml-basics.md")
    assert result["tags"] == ["ai", "machine-learning"]
    assert "Machine Learning Fundamentals" in result["title"]
    assert "supervised" in result["full_content"]
    assert result["has_metadata"] is True


def test_parse_note_without_frontmatter():
    """Notes without frontmatter still parse."""
    content = "# Quick Thought\n\nSome interesting idea about design."
    result = parse_obsidian_note(content, "quick-thought.md")
    assert result["title"] == "Quick Thought"
    assert result["has_metadata"] is False
    assert "design" in result["full_content"]


def test_parse_empty_note():
    """Empty notes return None."""
    result = parse_obsidian_note("", "empty.md")
    assert result is None


def test_parse_short_note():
    """Very short notes (< 20 chars) return None."""
    result = parse_obsidian_note("hi", "short.md")
    assert result is None
```

**Step 2: Run test to verify fails**

Run: `uv run pytest tests/test_import_parser.py -v`
Expected: FAIL — module not found

**Step 3: Implement parser**

Note: Use `import_vault` as the module name (not `import` which is a Python keyword).

Create `src/sieve/import_vault/__init__.py` (empty).

Create `src/sieve/import_vault/parser.py`:

```python
import re
import yaml


MIN_CONTENT_LENGTH = 20


def parse_obsidian_note(content: str, filename: str) -> dict | None:
    """Parse an Obsidian markdown note into a structured dict.

    Returns None if the note is empty or too short.
    """
    if not content or len(content.strip()) < MIN_CONTENT_LENGTH:
        return None

    frontmatter = {}
    body = content
    has_metadata = False

    # Extract YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
            has_metadata = bool(frontmatter.get("tags"))
        except yaml.YAMLError:
            pass
        body = content[fm_match.end():]

    # Extract title from first H1 or filename
    title = _extract_title(body, filename)

    # Extract tags
    tags = frontmatter.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]

    return {
        "title": title,
        "full_content": body.strip(),
        "tags": tags,
        "has_metadata": has_metadata,
        "frontmatter": frontmatter,
        "filename": filename,
    }


def _extract_title(body: str, filename: str) -> str:
    """Extract title from first heading or fall back to filename."""
    h1_match = re.match(r"^#\s+(.+)$", body.strip(), re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()
    # Fall back to filename without extension
    return re.sub(r"\.md$", "", filename).replace("-", " ").replace("_", " ").title()
```

**Step 4: Run test**

Run: `uv run pytest tests/test_import_parser.py -v`
Expected: PASS

**Step 5: Add pyyaml dependency**

Run: `uv add pyyaml`

**Step 6: Commit**

```bash
git add src/sieve/import_vault/ tests/test_import_parser.py pyproject.toml uv.lock
git commit -m "feat: add Obsidian markdown parser with frontmatter extraction"
```

---

### Task 18: Import API endpoint

**Files:**
- Create: `src/sieve/api/import_vault/__init__.py`
- Create: `src/sieve/api/import_vault/routes.py`
- Modify: `src/sieve/api/app.py`
- Test: `tests/test_import_api.py`

**Step 1: Write the failing test**

Create `tests/test_import_api.py`:

```python
import io
import zipfile

import pytest


def _make_vault_zip(notes: dict[str, str]) -> bytes:
    """Create a zip file with markdown notes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in notes.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_import_vault_zip(client, auth_cookies, mocker):
    """POST /api/import/vault accepts a zip and creates capsules."""
    # Mock LLM to avoid real API calls
    mocker.patch("sieve.llm.client.LLMClient.extract_capsule", return_value={
        "title": "Test Note",
        "executive_summary": "A test note",
        "core_insight": "Testing is good",
        "tags": ["test"],
        "keywords": ["test"],
        "topics": ["testing"],
        "category": "Technology",
        "domain": "tech",
        "difficulty": "beginner",
        "content_type": "insight",
        "source_type": "note",
    })

    vault_zip = _make_vault_zip({
        "note1.md": "---\ntags:\n  - ai\n---\n# AI Note\n\nThis is a note about artificial intelligence and its applications.",
        "note2.md": "# Design Note\n\nThoughts on good design principles and how to apply them.",
        "empty.md": "",
    })

    resp = await client.post(
        "/api/import/vault",
        cookies=auth_cookies,
        files={"file": ("vault.zip", vault_zip, "application/zip")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped"] == 1


@pytest.mark.asyncio
async def test_import_deduplicates(client, auth_cookies, db_session, test_user, mocker):
    """Import skips notes whose titles match existing capsules."""
    from sieve.db.models import Capsule
    _, sieve = test_user
    existing = Capsule(
        sieve_id=sieve.id, title="AI Note", executive_summary="s",
        core_insight="i", full_content="c",
    )
    db_session.add(existing)
    await db_session.commit()

    mocker.patch("sieve.llm.client.LLMClient.extract_capsule", return_value={
        "title": "AI Note", "executive_summary": "s", "core_insight": "i",
        "tags": [], "keywords": [], "topics": [], "category": "", "domain": "",
        "difficulty": "beginner", "content_type": "insight", "source_type": "note",
    })

    vault_zip = _make_vault_zip({
        "ai.md": "# AI Note\n\nDuplicate content about artificial intelligence.",
    })
    resp = await client.post(
        "/api/import/vault",
        cookies=auth_cookies,
        files={"file": ("vault.zip", vault_zip, "application/zip")},
    )
    data = resp.json()
    assert data["duplicates"] == 1
```

**Step 2: Run test to verify fails**

Run: `uv run pytest tests/test_import_api.py -v`
Expected: FAIL

**Step 3: Implement**

Create `src/sieve/api/import_vault/__init__.py` (empty).

Create `src/sieve/api/import_vault/routes.py`:

```python
import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, User
from sieve.import_vault.parser import parse_obsidian_note
from sieve.llm.client import LLMClient

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("/vault")
async def import_vault(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(400, "Please upload a .zip file")

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(400, "File too large (max 100 MB)")

    sieve = (await db.execute(select(Sieve).where(Sieve.user_id == user.id))).scalar_one_or_none()
    if not sieve:
        raise HTTPException(404, "Sieve not found")

    # Get existing titles for dedup
    existing_titles = set(
        (await db.execute(select(Capsule.title).where(Capsule.sieve_id == sieve.id))).scalars().all()
    )

    llm = LLMClient()
    imported = 0
    skipped = 0
    duplicates = 0

    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        md_files = [n for n in zf.namelist() if n.endswith(".md") and not n.startswith("__MACOSX")]
        for name in md_files:
            text = zf.read(name).decode("utf-8", errors="replace")
            parsed = parse_obsidian_note(text, name.split("/")[-1])
            if parsed is None:
                skipped += 1
                continue

            # For notes with good metadata, map directly
            if parsed["has_metadata"]:
                capsule_data = {
                    "title": parsed["title"],
                    "full_content": parsed["full_content"],
                    "tags": parsed["tags"],
                    "capture_method": "obsidian",
                }
                # Still need LLM for summary/insight/category
                llm_data = await llm.extract_capsule(parsed["full_content"])
                capsule_data.update({
                    k: llm_data[k] for k in [
                        "executive_summary", "core_insight", "keywords", "topics",
                        "category", "domain", "difficulty", "content_type", "source_type",
                    ] if k in llm_data
                })
                # Prefer parsed tags over LLM tags
                capsule_data["tags"] = parsed["tags"] or llm_data.get("tags", [])
            else:
                capsule_data = await llm.extract_capsule(parsed["full_content"])
                capsule_data["capture_method"] = "obsidian"

            # Dedup check
            title = capsule_data.get("title", parsed["title"])
            if title in existing_titles:
                duplicates += 1
                continue

            capsule = Capsule(sieve_id=sieve.id, **{
                k: v for k, v in capsule_data.items()
                if hasattr(Capsule, k)
            })
            capsule.full_content = parsed["full_content"]
            db.add(capsule)
            existing_titles.add(title)
            imported += 1

    await db.commit()
    return {"imported": imported, "skipped": skipped, "duplicates": duplicates, "total_files": len(md_files) if 'md_files' in dir() else 0}
```

Register in `src/sieve/api/app.py`:
```python
from sieve.api.import_vault.routes import router as import_router
app.include_router(import_router)
```

**Step 4: Add pytest-mock dependency if not present**

Run: `uv add --dev pytest-mock`

**Step 5: Run tests**

Run: `uv run pytest tests/test_import_api.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/sieve/api/import_vault/ src/sieve/api/app.py tests/test_import_api.py pyproject.toml uv.lock
git commit -m "feat: add vault import API (zip upload, LLM extraction, dedup)"
```

---

### Task 19: Import dashboard page

**Files:**
- Create: `src/sieve/dashboard/templates/import.html`
- Modify: `src/sieve/dashboard/routes.py`
- Modify: `src/sieve/dashboard/static/style.css`
- Test: `tests/test_dashboard.py`

**Step 1: Write test**

```python
def test_import_template_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/import.html")
```

**Step 2: Implement**

Create `src/sieve/dashboard/templates/import.html`:
- Page title: "Import from Obsidian"
- Instructions text explaining the import
- Two import options:
  1. Zip upload: drag-and-drop zone + file input, `<form hx-post="/api/import/vault" hx-encoding="multipart/form-data">`
  2. (Future) Folder select via File System Access API — show as "Coming soon"
- Progress indicator: `<div id="import-progress">` updated by HTMX response
- Results section: shows imported/skipped/duplicates counts

Add CSS for drop zone:
```css
.drop-zone {
    border: 2px dashed var(--border);
    border-radius: 12px;
    padding: 3rem;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s;
}
.drop-zone:hover, .drop-zone.dragover {
    border-color: var(--accent);
}
```

Add route: `GET /import` → renders `import.html` (protected)

**Step 3: Run tests, commit**

Run: `uv run pytest -v`

```bash
git add src/sieve/dashboard/ tests/test_dashboard.py
git commit -m "feat: add vault import page with drag-and-drop zip upload"
```

---

### Task 20: Final integration test

**Files:**
- Test: `tests/test_integration.py`

**Step 1: Write integration test**

```python
import pytest

from sieve.db.models import Capsule, Follow, Sieve, User


@pytest.mark.asyncio
async def test_full_social_flow(client, db_session):
    """End-to-end: signup, capture, make public, follow, see in feed."""
    # User 1 signs up
    resp = await client.post("/api/auth/signup", json={
        "email": "alice@test.com", "password": "pass123",
        "display_name": "Alice", "username": "alice",
    })
    assert resp.status_code == 201
    token1 = resp.json()["access_token"]
    cookies1 = {"sieve_token": token1}

    # User 1 captures a note
    resp = await client.post("/api/capsules/", cookies=cookies1, json={
        "title": "Alice's Insight",
        "executive_summary": "Great insight",
        "core_insight": "The key takeaway",
        "full_content": "Full content here",
        "tags": ["ai"],
    })
    assert resp.status_code == 201

    # User 1 makes sieve public
    resp = await client.put("/api/sieves/me", cookies=cookies1, json={"is_public": True})
    assert resp.status_code == 200

    # User 2 signs up
    resp = await client.post("/api/auth/signup", json={
        "email": "bob@test.com", "password": "pass123",
        "display_name": "Bob", "username": "bob",
    })
    token2 = resp.json()["access_token"]
    cookies2 = {"sieve_token": token2}

    # User 2 discovers Alice
    resp = await client.get("/api/discover/sieves")
    data = resp.json()
    assert any(s["username"] == "alice" for s in data["sieves"])

    # User 2 follows Alice
    resp = await client.post("/api/sieves/@alice/follow", cookies=cookies2)
    assert resp.status_code == 201

    # User 2 sees Alice's capsule in feed
    resp = await client.get("/api/feed/", cookies=cookies2)
    data = resp.json()
    assert any(c["title"] == "Alice's Insight" for c in data["capsules"])
```

**Step 2: Run integration test**

Run: `uv run pytest tests/test_integration.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add full social flow integration test"
```

---

## Summary

| Phase | Tasks | What's delivered |
|-------|-------|-----------------|
| **1. Social DB + API** | Tasks 1-7 | Follow model, username, sieve profiles, follow/unfollow, feed API, discover API |
| **2. Feed Dashboard** | Tasks 8-12 | Feed home page, discover page, sieve profiles, settings, mobile nav |
| **3. Sieve Clipper** | Tasks 13-16 | Forked Obsidian Clipper, rebranded, one-click capture, auth, toasts |
| **4. Vault Import** | Tasks 17-20 | Markdown parser, import API, dashboard page, integration test |

Total: **20 tasks**, each with TDD steps, exact file paths, and commit messages.
