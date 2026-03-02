# Capsule-to-Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to create persistent, editable skills from capsules, managed through a new Skills page with full CRUD, export, and MCP integration.

**Architecture:** New `Skill` and `SkillCapsule` DB models linked to capsules via many-to-many. Refactored compiler returns structured data for DB persistence. New `/skills` dashboard page + API endpoints. MCP server extended with skill tools.

**Tech Stack:** SQLAlchemy async ORM, Alembic, Pydantic v2, FastAPI, HTMX + Jinja2, MCP SDK

---

### Task 1: Add Skill and SkillCapsule database models

**Files:**
- Modify: `src/sieve/db/models.py:138` (after Capsule class)

**Step 1: Write the failing test**

Create `tests/test_skill_models.py`:

```python
import uuid

from sieve.db.models import Skill, SkillCapsule, Sieve


def test_skill_model_has_required_columns():
    skill = Skill(
        sieve_id=uuid.uuid4(),
        name="sieve-deep-work",
        title="Deep Work",
        description="Use when working on focus techniques",
        body="## Overview\nDeep work is...",
    )
    assert skill.name == "sieve-deep-work"
    assert skill.title == "Deep Work"
    assert skill.status == "active"
    assert skill.id is not None


def test_skill_capsule_association():
    assoc = SkillCapsule(
        skill_id=uuid.uuid4(),
        capsule_id=uuid.uuid4(),
        role="primary",
    )
    assert assoc.role == "primary"


def test_skill_default_values():
    skill = Skill(
        sieve_id=uuid.uuid4(),
        name="test",
        title="Test",
        description="desc",
        body="body",
    )
    assert skill.status == "active"
    assert skill.created_at is not None
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_skill_models.py -v`
Expected: FAIL with ImportError (Skill, SkillCapsule not defined)

**Step 3: Write the models**

Add to `src/sieve/db/models.py` after the Capsule class (after line 138):

```python
class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sieve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sieves.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sieve: Mapped["Sieve"] = relationship()
    capsule_links: Mapped[list["SkillCapsule"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )


class SkillCapsule(Base):
    __tablename__ = "skill_capsules"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    capsule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(50), default="primary")

    skill: Mapped["Skill"] = relationship(back_populates="capsule_links")
    capsule: Mapped["Capsule"] = relationship()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_skill_models.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/db/models.py tests/test_skill_models.py
git commit -m "feat: add Skill and SkillCapsule database models"
```

---

### Task 2: Create Alembic migration

**Files:**
- Create: `src/sieve/db/migrations/versions/<auto>_add_skills_tables.py`

**Step 1: Generate migration**

Run: `cd /Users/lucasfischer/Documents/Code/neural-sieve-v3 && uv run alembic revision --autogenerate -m "add skills tables"`

**Step 2: Review the generated migration**

Verify it creates `skills` and `skill_capsules` tables with correct columns and foreign keys.

**Step 3: Apply migration**

Run: `uv run alembic upgrade head`
Expected: Migration applies successfully

**Step 4: Commit**

```bash
git add src/sieve/db/migrations/
git commit -m "feat: add migration for skills and skill_capsules tables"
```

---

### Task 3: Add Pydantic schemas for skills

**Files:**
- Create: `src/sieve/api/skills/schemas.py`
- Create: `src/sieve/api/skills/__init__.py`

**Step 1: Write the failing test**

Create `tests/test_skill_schemas.py`:

```python
import uuid

from sieve.api.skills.schemas import SkillCompileRequest, SkillResponse, SkillUpdate


def test_compile_request_with_context():
    req = SkillCompileRequest(
        primary_capsule_id=uuid.uuid4(),
        context_capsule_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    assert len(req.context_capsule_ids) == 2


def test_compile_request_defaults():
    req = SkillCompileRequest(primary_capsule_id=uuid.uuid4())
    assert req.context_capsule_ids == []


def test_skill_update_partial():
    update = SkillUpdate(title="New Title")
    dumped = update.model_dump(exclude_unset=True)
    assert "title" in dumped
    assert "body" not in dumped


def test_skill_response():
    resp = SkillResponse(
        id=str(uuid.uuid4()),
        name="sieve-test",
        title="Test Skill",
        description="Use when testing",
        body="# Test",
        status="active",
        source_capsule_count=1,
        created_at="2026-03-02T00:00:00",
        updated_at="2026-03-02T00:00:00",
    )
    assert resp.name == "sieve-test"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_skill_schemas.py -v`
Expected: FAIL with ImportError

**Step 3: Create the schemas**

Create `src/sieve/api/skills/__init__.py` (empty).

Create `src/sieve/api/skills/schemas.py`:

```python
from uuid import UUID

from pydantic import BaseModel


class SkillCompileRequest(BaseModel):
    primary_capsule_id: UUID
    context_capsule_ids: list[UUID] = []


class SkillUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    body: str | None = None


class SkillResponse(BaseModel):
    id: str
    name: str
    title: str
    description: str
    body: str
    status: str
    source_capsule_count: int
    created_at: str
    updated_at: str


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]
    total: int
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_skill_schemas.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/skills/ tests/test_skill_schemas.py
git commit -m "feat: add Pydantic schemas for skills"
```

---

### Task 4: Refactor compiler to return structured data

**Files:**
- Modify: `src/sieve/compiler/compiler.py`
- Modify: `src/sieve/compiler/templates.py`

**Step 1: Write the failing test**

Create `tests/test_compiler_refactor.py`:

```python
import pytest

from sieve.compiler.compiler import SkillCompiler, _slugify


def test_slugify():
    assert _slugify("Deep Work Techniques") == "deep-work-techniques"
    assert _slugify("Hello! World?") == "hello-world"


@pytest.mark.asyncio
async def test_compile_capsule_returns_dict():
    """compile_capsule should return a dict with name, title, description, body."""
    compiler = SkillCompiler.__new__(SkillCompiler)

    # Mock the LLM calls
    async def fake_compile_single(capsule):
        return "## Overview\nFake skill body"

    async def fake_generate_description(title, summary):
        return "Use when testing skill compilation"

    compiler.compile_single = fake_compile_single
    compiler._generate_description = fake_generate_description

    capsule = {
        "title": "Deep Work",
        "executive_summary": "Focus techniques for productivity",
        "core_insight": "Deep work is valuable",
        "full_content": "Full content here",
        "tags": ["productivity", "focus"],
    }

    result = await compiler.compile_capsule(capsule)

    assert result["name"] == "sieve-deep-work"
    assert result["title"] == "Deep Work"
    assert result["description"] == "Use when testing skill compilation"
    assert "Fake skill body" in result["body"]


@pytest.mark.asyncio
async def test_compile_capsules_with_context():
    """compile_capsules should handle primary + context capsules."""
    compiler = SkillCompiler.__new__(SkillCompiler)

    async def fake_compile_single(capsule):
        return "## Overview\nSingle capsule skill"

    async def fake_compile_group(label, capsules):
        return f"## Overview\nGroup skill from {len(capsules)} capsules"

    async def fake_generate_description(title, summary):
        return "Use when testing"

    compiler.compile_single = fake_compile_single
    compiler.compile_group = fake_compile_group
    compiler._generate_description = fake_generate_description

    primary = {
        "title": "Primary Capsule",
        "executive_summary": "Primary summary",
        "core_insight": "Primary insight",
        "full_content": "Primary content",
        "tags": ["test"],
    }
    context = [
        {
            "title": "Context 1",
            "executive_summary": "Context summary",
            "core_insight": "Context insight",
            "full_content": "Context content",
            "tags": [],
        }
    ]

    result = await compiler.compile_capsules(primary, context_capsules=context)
    assert result["name"] == "sieve-primary-capsule"
    assert "2 capsules" in result["body"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_compiler_refactor.py -v`
Expected: FAIL (compile_capsule and compile_capsules methods don't exist)

**Step 3: Add new methods to SkillCompiler**

Add to `src/sieve/compiler/compiler.py` (new methods on the class, after `compile_group`):

```python
    async def compile_capsule(self, capsule: dict) -> dict:
        """Compile a single capsule into a skill data dict (not a file).

        Returns dict with keys: name, title, description, body.
        """
        title = capsule.get("title", "Untitled")
        slug = _slugify(title)
        name = f"sieve-{slug}"

        body = await self.compile_single(capsule)
        summary = capsule.get("executive_summary", title)
        description = await self._generate_description(title, summary)

        return {"name": name, "title": title, "description": description, "body": body}

    async def compile_capsules(
        self, primary: dict, context_capsules: list[dict] | None = None
    ) -> dict:
        """Compile a primary capsule with optional context capsules into a skill data dict.

        If context_capsules are provided, uses compile_group to synthesize all capsules.
        Otherwise, uses compile_single on the primary capsule alone.

        Returns dict with keys: name, title, description, body.
        """
        title = primary.get("title", "Untitled")
        slug = _slugify(title)
        name = f"sieve-{slug}"

        if context_capsules:
            all_capsules = [primary] + context_capsules
            body = await self.compile_group(title, all_capsules)
        else:
            body = await self.compile_single(primary)

        summary = primary.get("executive_summary", title)
        description = await self._generate_description(title, summary)

        return {"name": name, "title": title, "description": description, "body": body}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_compiler_refactor.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/compiler/compiler.py tests/test_compiler_refactor.py
git commit -m "feat: add compile_capsule and compile_capsules methods to SkillCompiler"
```

---

### Task 5: Add Skill API routes

**Files:**
- Create: `src/sieve/api/skills/routes.py`
- Modify: `src/sieve/api/app.py:39` (register router)

**Step 1: Write the failing test**

Create `tests/test_skill_routes.py`:

```python
def test_skill_routes_exist():
    from sieve.api.skills.routes import router

    paths = [r.path for r in router.routes]
    assert "/" in paths  # list
    assert "/{skill_id}" in paths  # get, update, delete
    assert "/compile" in paths
    assert "/{skill_id}/export" in paths
    assert "/{skill_id}/recompile" in paths
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_skill_routes.py -v`
Expected: FAIL with ImportError

**Step 3: Create the routes**

Create `src/sieve/api/skills/routes.py`:

```python
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.api.skills.schemas import (
    SkillCompileRequest,
    SkillListResponse,
    SkillResponse,
    SkillUpdate,
)
from sieve.compiler.compiler import SkillCompiler, _slugify
from sieve.compiler.templates import SKILL_TEMPLATE
from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, Skill, SkillCapsule, User

router = APIRouter(prefix="/api/skills", tags=["skills"])


def skill_to_response(s: Skill) -> SkillResponse:
    return SkillResponse(
        id=str(s.id),
        name=s.name,
        title=s.title,
        description=s.description,
        body=s.body,
        status=s.status or "active",
        source_capsule_count=len(s.capsule_links) if s.capsule_links else 0,
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else "",
    )


async def _get_user_sieve(user: User, db: AsyncSession) -> Sieve:
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sieve not found")
    return sieve


async def _get_skill_or_404(skill_id: str, sieve: Sieve, db: AsyncSession) -> Skill:
    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return skill


@router.post("/compile", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def compile_skill(
    body: SkillCompileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)

    # Load primary capsule
    result = await db.execute(
        select(Capsule).where(
            Capsule.id == body.primary_capsule_id, Capsule.sieve_id == sieve.id
        )
    )
    primary = result.scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary capsule not found")

    primary_dict = {
        "title": primary.title,
        "executive_summary": primary.executive_summary,
        "core_insight": primary.core_insight,
        "full_content": primary.full_content,
        "tags": primary.tags or [],
    }

    # Load context capsules
    context_dicts = []
    context_rows = []
    if body.context_capsule_ids:
        result = await db.execute(
            select(Capsule).where(
                Capsule.id.in_([str(cid) for cid in body.context_capsule_ids]),
                Capsule.sieve_id == sieve.id,
            )
        )
        context_rows = list(result.scalars().all())
        context_dicts = [
            {
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
            }
            for c in context_rows
        ]

    compiler = SkillCompiler(api_url="", api_key="")
    skill_data = await compiler.compile_capsules(primary_dict, context_capsules=context_dicts or None)

    skill = Skill(
        sieve_id=sieve.id,
        name=skill_data["name"],
        title=skill_data["title"],
        description=skill_data["description"],
        body=skill_data["body"],
    )
    db.add(skill)
    await db.flush()

    # Create associations
    db.add(SkillCapsule(skill_id=skill.id, capsule_id=primary.id, role="primary"))
    for c in context_rows:
        db.add(SkillCapsule(skill_id=skill.id, capsule_id=c.id, role="context"))

    await db.commit()
    await db.refresh(skill)

    return skill_to_response(skill)


@router.get("/", response_model=SkillListResponse)
async def list_skills(
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    query = select(Skill).where(Skill.sieve_id == sieve.id, Skill.status == "active")

    if search:
        term = f"%{search}%"
        query = query.where(
            or_(Skill.title.ilike(term), Skill.description.ilike(term), Skill.name.ilike(term))
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Skill.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    skills = result.scalars().all()

    return SkillListResponse(skills=[skill_to_response(s) for s in skills], total=total)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)
    return skill_to_response(skill)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    body: SkillUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)

    await db.commit()
    await db.refresh(skill)
    return skill_to_response(skill)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)
    await db.delete(skill)
    await db.commit()


@router.post("/{skill_id}/export")
async def export_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)

    output_dir = Path(".claude/skills")
    output_dir.mkdir(parents=True, exist_ok=True)

    content = SKILL_TEMPLATE.format(name=skill.name, description=skill.description, body=skill.body)
    path = output_dir / f"{skill.name}.md"
    path.write_text(content)

    return {"path": str(path), "message": f"Exported to {path}"}


@router.post("/{skill_id}/recompile", response_model=SkillResponse)
async def recompile_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)

    # Load linked capsules
    result = await db.execute(
        select(SkillCapsule).where(SkillCapsule.skill_id == skill.id)
    )
    links = result.scalars().all()

    if not links:
        raise HTTPException(status_code=400, detail="No linked capsules to recompile from")

    primary_link = next((l for l in links if l.role == "primary"), links[0])
    context_links = [l for l in links if l.skill_id == skill.id and l.capsule_id != primary_link.capsule_id]

    # Load capsule data
    result = await db.execute(select(Capsule).where(Capsule.id == primary_link.capsule_id))
    primary = result.scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=400, detail="Primary capsule no longer exists")

    primary_dict = {
        "title": primary.title,
        "executive_summary": primary.executive_summary,
        "core_insight": primary.core_insight,
        "full_content": primary.full_content,
        "tags": primary.tags or [],
    }

    context_dicts = []
    if context_links:
        ctx_ids = [l.capsule_id for l in context_links]
        result = await db.execute(select(Capsule).where(Capsule.id.in_(ctx_ids)))
        for c in result.scalars().all():
            context_dicts.append({
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
            })

    compiler = SkillCompiler(api_url="", api_key="")
    skill_data = await compiler.compile_capsules(primary_dict, context_capsules=context_dicts or None)

    skill.body = skill_data["body"]
    skill.description = skill_data["description"]
    await db.commit()
    await db.refresh(skill)

    return skill_to_response(skill)
```

**Step 4: Register the router in app.py**

In `src/sieve/api/app.py`, add import and include:

```python
from sieve.api.skills.routes import router as skills_router
```

And after `app.include_router(capture_router)` (line 40), add:

```python
    app.include_router(skills_router)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_skill_routes.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/sieve/api/skills/routes.py src/sieve/api/app.py tests/test_skill_routes.py
git commit -m "feat: add Skill API routes (CRUD, compile, export, recompile)"
```

---

### Task 6: Add Skills dashboard page route and template

**Files:**
- Modify: `src/sieve/dashboard/routes.py`
- Create: `src/sieve/dashboard/templates/skills.html`
- Create: `src/sieve/dashboard/templates/partials/skill_card.html`
- Create: `src/sieve/dashboard/templates/partials/skill_grid.html`

**Step 1: Write the failing test**

Add to `tests/test_dashboard.py`:

```python
def test_skills_route_exists():
    from sieve.dashboard.routes import router

    paths = [r.path for r in router.routes]
    assert "/skills" in paths


def test_skill_detail_route_exists():
    from sieve.dashboard.routes import router

    paths = [r.path for r in router.routes]
    assert "/skills/{skill_id}" in paths


def test_skills_templates_exist():
    templates_dir = Path("src/sieve/dashboard/templates")
    assert (templates_dir / "skills.html").exists()
    assert (templates_dir / "skill_detail.html").exists()
    assert (templates_dir / "partials" / "skill_card.html").exists()
    assert (templates_dir / "partials" / "skill_grid.html").exists()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard.py::test_skills_route_exists -v`
Expected: FAIL

**Step 3: Add the route**

Add to `src/sieve/dashboard/routes.py` (after the compile_page route, around line 88):

```python
@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request):
    return _protected(request, "skills.html")


@router.get("/skills/{skill_id}", response_class=HTMLResponse)
async def skill_detail(
    request: Request, skill_id: str, db: AsyncSession = Depends(get_db)
):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    user_id = verify_token(request.cookies.get("sieve_token"))
    result = await db.execute(select(Sieve).where(Sieve.user_id == user_id))
    sieve = result.scalar_one_or_none()

    skill = None
    source_capsules = []
    if sieve:
        from sieve.db.models import Skill, SkillCapsule
        result = await db.execute(
            select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
        )
        row = result.scalar_one_or_none()
        if row:
            from sieve.api.skills.routes import skill_to_response
            skill = skill_to_response(row).model_dump()

            # Load source capsules
            result = await db.execute(
                select(SkillCapsule).where(SkillCapsule.skill_id == row.id)
            )
            links = result.scalars().all()
            for link in links:
                cap_result = await db.execute(
                    select(Capsule).where(Capsule.id == link.capsule_id)
                )
                cap = cap_result.scalar_one_or_none()
                if cap:
                    source_capsules.append({
                        "id": str(cap.id),
                        "title": cap.title,
                        "role": link.role,
                    })

    return _render(
        request, "skill_detail.html",
        {"skill": skill, "skill_id": skill_id, "source_capsules": source_capsules},
    )
```

Add `Skill, SkillCapsule` to the models import at line 10:

```python
from sieve.db.models import Capsule, Sieve, Skill, SkillCapsule
```

Add the `_protected` auth check test for the new routes in the test:

```python
def test_protected_routes_have_auth_check():
    import inspect
    from sieve.dashboard.routes import sieve_page, capture_page, discover_page, compile_page, capsule_detail, skills_page, skill_detail

    for fn in [sieve_page, capture_page, discover_page, compile_page, capsule_detail, skills_page, skill_detail]:
        source = inspect.getsource(fn)
        assert "_protected" in source or "_is_authenticated" in source, f"{fn.__name__} missing auth check"
```

**Step 4: Create templates**

Create `src/sieve/dashboard/templates/skills.html`:

```html
{% extends "base.html" %}
{% block title %}Skills — Neural Sieve{% endblock %}
{% block content %}
<div class="toolbar">
    <div class="search-box">
        <input
            type="search"
            name="search"
            placeholder="Search skills..."
            class="input search-input"
            hx-get="/htmx/skills/"
            hx-trigger="input changed delay:300ms, search"
            hx-target="#skill-grid"
        >
    </div>
</div>

<div id="skill-grid" class="card-grid"
     hx-get="/htmx/skills/"
     hx-trigger="load"
     hx-swap="innerHTML">
    {% include "partials/skeleton_grid.html" %}
</div>
{% endblock %}
```

Create `src/sieve/dashboard/templates/partials/skill_card.html`:

```html
<a href="/skills/{{ skill.id }}" class="card capsule-card" hx-boost="true">
    <div class="card-header">
        <span class="badge">Skill</span>
    </div>
    <h3 class="card-title">{{ skill.title }}</h3>
    <p class="card-summary">{{ skill.description }}</p>
    <div class="card-meta">
        {% if skill.created_at %}<span>{{ skill.created_at[:10] }}</span>{% endif %}
        <span class="meta-sep">{{ skill.source_capsule_count }} capsule{{ 's' if skill.source_capsule_count != 1 else '' }}</span>
    </div>
</a>
```

Create `src/sieve/dashboard/templates/partials/skill_grid.html`:

```html
{% if search_term %}
<div class="search-results-count" style="grid-column: 1 / -1;">
    <strong>{{ count }}</strong> result{{ 's' if count != 1 else '' }} for &ldquo;{{ search_term }}&rdquo;
</div>
{% endif %}
{% if skills %}
    {% for skill in skills %}
    {% include "partials/skill_card.html" %}
    {% endfor %}
{% else %}
    <div class="empty-state">
        <div class="empty-icon">&#9889;</div>
        <h3>No skills yet</h3>
        <p>Create a skill from any capsule in your sieve.</p>
    </div>
{% endif %}
```

Create `src/sieve/dashboard/templates/skill_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{% if skill %}{{ skill.title }}{% else %}Skill{% endif %} — Neural Sieve{% endblock %}
{% block content %}
{% if skill %}
<article class="capsule-detail">
    <header class="capsule-header">
        <div class="capsule-header-top">
            <a href="/skills" class="back-link" hx-boost="true">&larr; Back to Skills</a>
            <div class="capsule-actions">
                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('edit-section').classList.toggle('hidden')">Edit</button>
                <button
                    class="btn btn-secondary btn-sm"
                    hx-post="/htmx/skills/{{ skill.id }}/export"
                    hx-swap="innerHTML"
                    hx-target="#export-result"
                >Export</button>
                <button
                    class="btn btn-secondary btn-sm"
                    hx-post="/htmx/skills/{{ skill.id }}/recompile"
                    hx-swap="none"
                    hx-confirm="Re-compile this skill from its source capsules?"
                >Re-compile</button>
                <button
                    class="btn btn-danger btn-sm"
                    hx-delete="/htmx/skills/{{ skill.id }}"
                    hx-confirm="Delete this skill? This cannot be undone."
                    hx-target="body"
                    hx-swap="innerHTML"
                >Delete</button>
            </div>
        </div>
        <div class="capsule-meta-bar">
            <span class="meta-item">{{ skill.name }}</span>
        </div>
        <h1 class="capsule-title">{{ skill.title }}</h1>
    </header>

    <section class="capsule-section">
        <h2 class="section-heading">Description</h2>
        <p class="capsule-content">{{ skill.description }}</p>
    </section>

    <section class="capsule-section">
        <h2 class="section-heading">Skill Body</h2>
        <div class="capsule-content skill-body">{{ skill.body }}</div>
    </section>

    {% if source_capsules %}
    <section class="capsule-section">
        <h2 class="section-heading">Source Capsules</h2>
        <div class="tag-list">
            {% for sc in source_capsules %}
            <a href="/capsule/{{ sc.id }}" class="tag-chip" hx-boost="true">{{ sc.title }} ({{ sc.role }})</a>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    <div id="export-result"></div>

    <footer class="capsule-footer">
        <span>Created {{ skill.created_at[:10] if skill.created_at else "" }}</span>
        <span>Updated {{ skill.updated_at[:10] if skill.updated_at else "" }}</span>
    </footer>
</article>

<section id="edit-section" class="edit-section hidden">
    <h2 class="section-heading">Edit Skill</h2>
    <form
        hx-put="/htmx/skills/{{ skill.id }}"
        hx-target="body"
        hx-swap="innerHTML"
    >
        <div class="form-group">
            <label class="form-label" for="edit-title">Title</label>
            <input type="text" id="edit-title" name="title" value="{{ skill.title }}" class="input">
        </div>
        <div class="form-group">
            <label class="form-label" for="edit-description">Description</label>
            <textarea id="edit-description" name="description" rows="3" class="input textarea">{{ skill.description }}</textarea>
        </div>
        <div class="form-group">
            <label class="form-label" for="edit-body">Body</label>
            <textarea id="edit-body" name="body" rows="12" class="input textarea" style="font-family: 'SF Mono', monospace; font-size: 0.8125rem;">{{ skill.body }}</textarea>
        </div>
        <div class="form-actions">
            <button type="submit" class="btn btn-primary">Save</button>
            <button type="button" class="btn btn-secondary" onclick="document.getElementById('edit-section').classList.add('hidden')">Cancel</button>
        </div>
    </form>
</section>

{% else %}
<div class="empty-state">
    <a href="/skills" class="back-link" hx-boost="true">&larr; Back to Skills</a>
    <div class="empty-icon">&#9889;</div>
    <h3>Skill not found</h3>
    <p>The skill with ID <code>{{ skill_id }}</code> could not be loaded.</p>
</div>
{% endif %}
{% endblock %}
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/sieve/dashboard/routes.py src/sieve/dashboard/templates/skills.html src/sieve/dashboard/templates/skill_detail.html src/sieve/dashboard/templates/partials/skill_card.html src/sieve/dashboard/templates/partials/skill_grid.html tests/test_dashboard.py
git commit -m "feat: add Skills dashboard page, skill detail page, and templates"
```

---

### Task 7: Add HTMX routes for skills

**Files:**
- Modify: `src/sieve/dashboard/htmx_routes.py`

**Step 1: Write the failing test**

Add to `tests/test_dashboard.py`:

```python
def test_htmx_skill_routes_exist():
    from sieve.dashboard.htmx_routes import router

    paths = [r.path for r in router.routes]
    assert "/skills/" in paths
    assert "/skills/compile" in paths
    assert "/skills/{skill_id}" in paths
    assert "/skills/{skill_id}/export" in paths
    assert "/skills/{skill_id}/recompile" in paths
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dashboard.py::test_htmx_skill_routes_exist -v`
Expected: FAIL

**Step 3: Add HTMX routes**

Add to `src/sieve/dashboard/htmx_routes.py` (after the `htmx_delete_capsule` function):

```python
# ---------------------------------------------------------------------------
# Skill routes
# ---------------------------------------------------------------------------


@router.get("/skills/", response_class=HTMLResponse)
async def htmx_list_skills(
    request: Request,
    search: str | None = Query(None),
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.api.skills.routes import skill_to_response
    from sieve.db.models import Skill

    query = select(Skill).where(Skill.sieve_id == sieve.id, Skill.status == "active")

    if search:
        term = f"%{search}%"
        query = query.where(
            or_(Skill.title.ilike(term), Skill.description.ilike(term), Skill.name.ilike(term))
        )

    query = query.order_by(Skill.created_at.desc()).limit(50)
    result = await db.execute(query)
    skills = result.scalars().all()

    skill_dicts = [skill_to_response(s).model_dump() for s in skills]

    return _render_partial(
        "partials/skill_grid.html",
        skills=skill_dicts,
        count=len(skill_dicts),
        search_term=search or "",
    )


@router.post("/skills/compile", response_class=HTMLResponse)
async def htmx_compile_skill(
    request: Request,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.api.skills.routes import skill_to_response
    from sieve.compiler.compiler import SkillCompiler
    from sieve.db.models import Skill, SkillCapsule

    form = await request.form()
    primary_id = form.get("primary_capsule_id", "")
    context_ids_raw = form.get("context_capsule_ids", "")
    context_ids = [cid.strip() for cid in context_ids_raw.split(",") if cid.strip()]

    if not primary_id:
        return HTMLResponse(
            content='<div class="alert alert-error">Primary capsule is required</div>',
            status_code=400,
        )

    # Load primary capsule
    result = await db.execute(
        select(Capsule).where(Capsule.id == primary_id, Capsule.sieve_id == sieve.id)
    )
    primary = result.scalar_one_or_none()
    if not primary:
        return HTMLResponse(
            content='<div class="alert alert-error">Capsule not found</div>',
            status_code=404,
        )

    primary_dict = {
        "title": primary.title,
        "executive_summary": primary.executive_summary,
        "core_insight": primary.core_insight,
        "full_content": primary.full_content,
        "tags": primary.tags or [],
    }

    context_dicts = []
    context_rows = []
    if context_ids:
        result = await db.execute(
            select(Capsule).where(Capsule.id.in_(context_ids), Capsule.sieve_id == sieve.id)
        )
        context_rows = list(result.scalars().all())
        context_dicts = [
            {
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
            }
            for c in context_rows
        ]

    if not settings.openai_api_key:
        return HTMLResponse(
            content='<div class="alert alert-error">SIEVE_OPENAI_API_KEY is not set</div>',
            status_code=500,
        )

    compiler = SkillCompiler(api_url="", api_key="")
    try:
        skill_data = await compiler.compile_capsules(primary_dict, context_capsules=context_dicts or None)
    except Exception as e:
        return HTMLResponse(
            content=f'<div class="alert alert-error">{e}</div>',
            status_code=500,
        )

    skill = Skill(
        sieve_id=sieve.id,
        name=skill_data["name"],
        title=skill_data["title"],
        description=skill_data["description"],
        body=skill_data["body"],
    )
    db.add(skill)
    await db.flush()

    db.add(SkillCapsule(skill_id=skill.id, capsule_id=primary.id, role="primary"))
    for c in context_rows:
        db.add(SkillCapsule(skill_id=skill.id, capsule_id=c.id, role="context"))

    await db.commit()
    await db.refresh(skill)

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/skills/{skill.id}"
    return response


@router.put("/skills/{skill_id}", response_class=HTMLResponse)
async def htmx_update_skill(
    request: Request,
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.db.models import Skill

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    form = await request.form()
    for field in ["title", "description", "body"]:
        value = form.get(field)
        if value is not None:
            setattr(skill, field, value)

    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/skills/{skill_id}"
    return response


@router.delete("/skills/{skill_id}", response_class=HTMLResponse)
async def htmx_delete_skill(
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.db.models import Skill

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    await db.delete(skill)
    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = "/skills"
    return response


@router.post("/skills/{skill_id}/export", response_class=HTMLResponse)
async def htmx_export_skill(
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from pathlib import Path

    from sieve.compiler.templates import SKILL_TEMPLATE
    from sieve.db.models import Skill

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    output_dir = Path(".claude/skills")
    output_dir.mkdir(parents=True, exist_ok=True)
    content = SKILL_TEMPLATE.format(name=skill.name, description=skill.description, body=skill.body)
    path = output_dir / f"{skill.name}.md"
    path.write_text(content)

    return HTMLResponse(
        content=f'<div class="alert alert-success">Exported to {path}</div>'
    )


@router.post("/skills/{skill_id}/recompile", response_class=HTMLResponse)
async def htmx_recompile_skill(
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.compiler.compiler import SkillCompiler
    from sieve.db.models import Skill, SkillCapsule

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    # Load linked capsules
    result = await db.execute(
        select(SkillCapsule).where(SkillCapsule.skill_id == skill.id)
    )
    links = result.scalars().all()
    if not links:
        return HTMLResponse(content='<div class="alert alert-error">No linked capsules</div>')

    primary_link = next((l for l in links if l.role == "primary"), links[0])
    context_links = [l for l in links if l.capsule_id != primary_link.capsule_id]

    result = await db.execute(select(Capsule).where(Capsule.id == primary_link.capsule_id))
    primary = result.scalar_one_or_none()
    if not primary:
        return HTMLResponse(content='<div class="alert alert-error">Primary capsule deleted</div>')

    primary_dict = {
        "title": primary.title,
        "executive_summary": primary.executive_summary,
        "core_insight": primary.core_insight,
        "full_content": primary.full_content,
        "tags": primary.tags or [],
    }

    context_dicts = []
    if context_links:
        ctx_ids = [l.capsule_id for l in context_links]
        result = await db.execute(select(Capsule).where(Capsule.id.in_(ctx_ids)))
        for c in result.scalars().all():
            context_dicts.append({
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
            })

    compiler = SkillCompiler(api_url="", api_key="")
    try:
        skill_data = await compiler.compile_capsules(primary_dict, context_capsules=context_dicts or None)
    except Exception as e:
        return HTMLResponse(content=f'<div class="alert alert-error">{e}</div>')

    skill.body = skill_data["body"]
    skill.description = skill_data["description"]
    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/skills/{skill_id}"
    return response
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/dashboard/htmx_routes.py tests/test_dashboard.py
git commit -m "feat: add HTMX routes for skill CRUD, compile, export, recompile"
```

---

### Task 8: Add "Create Skill" button to capsule detail and update navigation

**Files:**
- Modify: `src/sieve/dashboard/templates/capsule_detail.html`
- Modify: `src/sieve/dashboard/templates/base.html`

**Step 1: Add Skills nav link to base.html**

In `src/sieve/dashboard/templates/base.html`, add a Skills link in the nav-links div (line 21, after Compile):

```html
            <a href="/skills" hx-boost="true">Skills</a>
```

**Step 2: Add "Create Skill" section to capsule_detail.html**

In `src/sieve/dashboard/templates/capsule_detail.html`, after the Delete button (line 24), add a Create Skill button:

```html
                <button class="btn btn-primary btn-sm" onclick="document.getElementById('create-skill-section').classList.toggle('hidden')">Create Skill</button>
```

Then after the edit-section (after line 89), add the Create Skill form section:

```html
<section id="create-skill-section" class="edit-section hidden">
    <h2 class="section-heading">Create Skill from Capsule</h2>
    <p style="font-size: 0.8125rem; color: #86868b; margin-bottom: 1rem;">
        This capsule will be the primary source. Optionally add more capsules as context.
    </p>
    <form
        hx-post="/htmx/skills/compile"
        hx-target="body"
        hx-swap="innerHTML"
    >
        <input type="hidden" name="primary_capsule_id" value="{{ capsule.id }}">
        <div class="form-group">
            <label class="form-label" for="context-ids">Additional Capsule IDs (comma-separated, optional)</label>
            <input type="text" id="context-ids" name="context_capsule_ids" class="input" placeholder="e.g. abc123, def456">
        </div>
        <div class="form-actions">
            <button type="submit" class="btn btn-primary">
                <span class="htmx-indicator spinner"></span>
                Compile Skill
            </button>
            <button type="button" class="btn btn-secondary" onclick="document.getElementById('create-skill-section').classList.add('hidden')">Cancel</button>
        </div>
    </form>
</section>
```

**Step 3: Write test to verify nav link**

Add to `tests/test_dashboard.py`:

```python
def test_base_template_has_skills_nav():
    html = Path("src/sieve/dashboard/templates/base.html").read_text()
    assert "/skills" in html


def test_capsule_detail_has_create_skill():
    html = Path("src/sieve/dashboard/templates/capsule_detail.html").read_text()
    assert "create-skill-section" in html
    assert "primary_capsule_id" in html
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/dashboard/templates/base.html src/sieve/dashboard/templates/capsule_detail.html tests/test_dashboard.py
git commit -m "feat: add Skills nav link and Create Skill button on capsule detail"
```

---

### Task 9: Add CSS for skill-specific elements

**Files:**
- Modify: `src/sieve/dashboard/static/style.css`

**Step 1: Add skill body styling**

Append to `src/sieve/dashboard/static/style.css` (before the responsive section at line 853):

```css
/* --- Skill Body ------------------------------------------------------ */

.skill-body {
    font-family: "SF Mono", "Fira Code", Menlo, Consolas, monospace;
    font-size: 0.8125rem;
    line-height: 1.6;
    white-space: pre-wrap;
    background: #f5f5f7;
    padding: 1rem;
    border-radius: 8px;
    overflow-x: auto;
}
```

**Step 2: Commit**

```bash
git add src/sieve/dashboard/static/style.css
git commit -m "feat: add CSS for skill body display"
```

---

### Task 10: Add MCP tools for skills

**Files:**
- Modify: `src/sieve/mcp/server.py`
- Modify: `src/sieve/mcp/api_client.py`

**Step 1: Write the failing test**

Create `tests/test_mcp_skills.py`:

```python
def test_mcp_tools_include_skills():
    from sieve.mcp.server import TOOLS

    tool_names = [t.name for t in TOOLS]
    assert "search_skills" in tool_names
    assert "get_skill" in tool_names


def test_api_client_has_skill_methods():
    from sieve.mcp.api_client import SieveAPIClient

    client = SieveAPIClient(api_url="http://localhost:8421", api_key="test")
    assert hasattr(client, "list_skills")
    assert hasattr(client, "get_skill")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_mcp_skills.py -v`
Expected: FAIL

**Step 3: Add skill methods to api_client.py**

Add to `src/sieve/mcp/api_client.py` (after `get_index` method):

```python
    async def list_skills(self, **params) -> dict:
        """List skills with optional filters."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/skills/",
                params=params,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_skill(self, skill_id: str) -> dict:
        """Get a specific skill by ID."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.api_url}/api/skills/{skill_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
```

**Step 4: Add tools and handlers to server.py**

Add two new Tool definitions to the TOOLS list in `src/sieve/mcp/server.py` (after `get_index` tool):

```python
    Tool(
        name="search_skills",
        description=(
            "Search the user's skills. Skills are compiled from capsules and contain "
            "actionable knowledge formatted as Claude Code skills."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for skill name or description",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_skill",
        description="Get a specific skill by ID. Returns the full skill content as SKILL.md-compatible markdown.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The skill ID",
                },
            },
            "required": ["id"],
        },
    ),
```

Add a format helper for skills after `format_index`:

```python
def format_skill(s: dict) -> str:
    """Format a skill as SKILL.md-compatible markdown."""
    lines = [
        "---",
        f"name: {s.get('name', 'unnamed')}",
        f"description: {s.get('description', '')}",
        "---",
        "",
        s.get("body", ""),
    ]
    return "\n".join(lines)


def format_skill_list(data: dict) -> str:
    """Format a list of skills as a bullet list."""
    skills = data.get("skills", [])
    total = data.get("total", len(skills))

    if not skills:
        return "No skills found."

    lines = [f"Found {total} skill{'s' if total != 1 else ''}:\n"]
    for s in skills:
        name = s.get("name", "unnamed")
        title = s.get("title", "Untitled")
        desc = s.get("description", "")[:100]
        skill_id = s.get("id", "?")
        lines.append(f"- **{title}** (`{name}`) — {desc} — ID: {skill_id}")

    return "\n".join(lines)
```

Add handlers in `handle_call_tool` (before the `else` clause):

```python
        elif name == "search_skills":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            data = await client.list_skills(search=query, limit=limit)
            text = format_skill_list(data)

        elif name == "get_skill":
            skill_id = arguments.get("id", "")
            data = await client.get_skill(skill_id)
            text = format_skill(data)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_mcp_skills.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/sieve/mcp/server.py src/sieve/mcp/api_client.py tests/test_mcp_skills.py
git commit -m "feat: add search_skills and get_skill MCP tools"
```

---

### Task 11: Run full test suite and verify

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Verify the server starts**

Run: `uv run sieve serve` (briefly, then Ctrl+C)
Expected: Server starts without import errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address test failures from skill feature integration"
```
