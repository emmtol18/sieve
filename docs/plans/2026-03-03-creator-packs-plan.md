# Creator Packs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename "leader" → "creator" globally, make capsule destination either/or (personal sieve XOR creator pack), and add a "Save to My Sieve" endpoint for users to copy creator capsules.

**Architecture:** Database migration renames `leaders` → `creators` and makes `capsules.sieve_id` nullable. Capture route branches on `creator_id` presence. New `/api/capsules/{id}/save` endpoint copies creator capsules to personal sieves.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, Pydantic v2, TypeScript (extension), HTMX + Jinja2 (dashboard)

---

### Task 1: Database migration — rename table + nullable sieve_id

**Files:**
- Create: `src/sieve/db/migrations/versions/005_rename_leaders_to_creators.py`

**Step 1: Write the migration**

```python
"""rename_leaders_to_creators_and_nullable_sieve_id

Revision ID: 005
Revises: 004
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop FK constraints referencing leaders
    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")

    # 2. Rename table
    op.rename_table("leaders", "creators")

    # 3. Re-create FK constraints pointing to creators
    op.create_foreign_key(
        "capsules_pack_id_fkey", "capsules", "creators",
        ["pack_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "subscriptions_pack_id_fkey", "subscriptions", "creators",
        ["pack_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "reviews_pack_id_fkey", "reviews", "creators",
        ["pack_id"], ["id"], ondelete="CASCADE",
    )

    # 4. Make capsules.sieve_id nullable (creator pack capsules have no personal sieve)
    op.alter_column("capsules", "sieve_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("capsules", "sieve_id", existing_type=sa.UUID(), nullable=False)

    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")

    op.rename_table("creators", "leaders")

    op.create_foreign_key(
        "capsules_pack_id_fkey", "capsules", "leaders",
        ["pack_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "subscriptions_pack_id_fkey", "subscriptions", "leaders",
        ["pack_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "reviews_pack_id_fkey", "reviews", "leaders",
        ["pack_id"], ["id"], ondelete="CASCADE",
    )
```

**Step 2: Run migration**

Run: `uv run alembic upgrade head`
Expected: `Running upgrade 004 -> 005`

**Step 3: Verify**

Run: `psql -d neural_sieve_v3 -c "\dt creators"` (use full psql path)
Expected: `creators` table exists, `leaders` does not

**Step 4: Commit**

```bash
git add src/sieve/db/migrations/versions/005_rename_leaders_to_creators.py
git commit -m "migrate: rename leaders to creators, make sieve_id nullable"
```

---

### Task 2: Rename Python model, schemas, and API module

**Files:**
- Modify: `src/sieve/db/models.py` — rename class `Leader` → `Creator`, `__tablename__` → `"creators"`, all relationship refs
- Modify: `src/sieve/api/leaders/schemas.py` → rename to `src/sieve/api/creators/schemas.py` — rename all `Leader*` → `Creator*`
- Modify: `src/sieve/api/leaders/routes.py` → rename to `src/sieve/api/creators/routes.py` — rename all functions, variables, imports, route prefix
- Modify: `src/sieve/api/leaders/__init__.py` → rename to `src/sieve/api/creators/__init__.py`
- Modify: `src/sieve/api/capsules/schemas.py` — rename `leader_id` → `creator_id` in CaptureRequest
- Modify: `src/sieve/db/models.py` — make `Capsule.sieve_id` nullable in the model

**Step 1: Rename model in models.py**

In `src/sieve/db/models.py`:
- `class Leader(Base):` → `class Creator(Base):`
- `__tablename__ = "leaders"` → `__tablename__ = "creators"`
- `Capsule.pack: Mapped["Leader | None"]` → `Mapped["Creator | None"]`
- `Subscription.pack: Mapped["Leader"]` → `Mapped["Creator"]`
- `Review.pack: Mapped["Leader"]` → `Mapped["Creator"]`
- `ForeignKey("leaders.id"` → `ForeignKey("creators.id"` (3 occurrences: capsules, subscriptions, reviews)
- Make `Capsule.sieve_id` nullable: change `nullable=False` → `nullable=True` and type to `Mapped[uuid.UUID | None]`

**Step 2: Rename the API module directory**

```bash
mv src/sieve/api/leaders src/sieve/api/creators
```

**Step 3: Rename schemas in `src/sieve/api/creators/schemas.py`**

Global replace in file:
- `LeaderCreate` → `CreatorCreate`
- `LeaderUpdate` → `CreatorUpdate`
- `LeaderResponse` → `CreatorResponse`
- `LeaderListResponse` → `CreatorListResponse`
- `leaders: list[` → `creators: list[`

**Step 4: Rename routes in `src/sieve/api/creators/routes.py`**

- All imports: `from sieve.api.creators.schemas import (CreatorCreate, CreatorListResponse, CreatorResponse, CreatorUpdate)`
- Import model: `from sieve.db.models import ... Creator ...` (not `Leader`)
- `router = APIRouter(prefix="/api/creators", tags=["creators"])`
- `def leader_to_response(leader: Leader)` → `def creator_to_response(creator: Creator) -> CreatorResponse:`
- All function names: `list_leaders` → `list_creators`, `get_leader` → `get_creator`, `create_leader` → `create_creator`, `update_leader` → `update_creator`, `delete_leader` → `delete_creator`, `get_leader_capsules` → `get_creator_capsules`
- All local variable names: `leader` → `creator`, `leaders` → `creators`
- Error messages: `"leader"` → `"creator"`

**Step 5: Rename `leader_id` in CaptureRequest**

In `src/sieve/api/capsules/schemas.py`:
- `leader_id: str | None = None` → `creator_id: str | None = None`

**Step 6: Run tests to check import errors**

Run: `uv run python -c "from sieve.db.models import Creator; print('OK')"`
Expected: `OK`

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor: rename leader to creator in models, schemas, API routes"
```

---

### Task 3: Update app registration, capture route, dashboard routes, HTMX routes, CLI

**Files:**
- Modify: `src/sieve/api/app.py` — update router import
- Modify: `src/sieve/api/capture/routes.py` — rename `Leader` → `Creator`, `leader_id` → `creator_id`
- Modify: `src/sieve/dashboard/routes.py` — rename leader imports, route path, function name
- Modify: `src/sieve/dashboard/htmx_routes.py` — rename leader imports, routes, functions
- Modify: `src/sieve/cli.py` — rename `seed-leaders` → `seed-creators`, `Leader` → `Creator`

**Step 1: Update app.py**

```python
from sieve.api.creators.routes import router as creators_router
# ...
app.include_router(creators_router)
```

**Step 2: Update capture/routes.py**

- `from sieve.db.models import Capsule, Creator, Sieve, User` (was `Leader`)
- `if body.creator_id:` (was `body.leader_id`)
- `result = await db.execute(select(Creator).where(Creator.id == body.creator_id))`
- `capsule.pack_id = creator.id`
- `if body.creator_id and creator:` for count update
- `select(func.count()).where(Capsule.pack_id == body.creator_id)`

**Step 3: Implement either/or capture logic in capture/routes.py**

Replace the capsule creation block:
```python
# Either/or: creator pack capsules don't belong to a personal sieve
if body.creator_id:
    result = await db.execute(select(Creator).where(Creator.id == body.creator_id))
    creator = result.scalar_one_or_none()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    capsule.pack_id = creator.id
    capsule.sieve_id = None  # belongs to creator, not personal sieve
else:
    # Personal sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(status_code=404, detail="Sieve not found for user")
    capsule.sieve_id = sieve.id
```

Note: the sieve lookup should move inside the else branch since creator pack capsules don't need it.

**Step 4: Update dashboard/routes.py**

- `from sieve.api.creators.routes import creator_to_response`
- Route: `@router.get("/creator/{slug}", ...)` (was `/leader/{slug}`)
- Function: `async def creator_profile(...)` (was `leader_profile`)
- Variable: `creator_obj`, `creator_dict`
- Template: `"creator.html"` with `{"creator": creator_dict}`

**Step 5: Update dashboard/htmx_routes.py**

- `from sieve.api.creators.routes import creator_to_response`
- Route: `@router.get("/creators/", ...)` (was `/leaders/`)
- Route: `@router.get("/creators/{slug}/capsules/", ...)` (was `/leaders/{slug}/capsules/`)
- Functions: `htmx_list_creators`, `htmx_creator_capsules`
- Variables: `creators`, `creator_dicts`
- Template: `"partials/creator_grid.html"` with `creators=creator_dicts`

**Step 6: Update cli.py**

- `@cli.command("seed-creators")` (was `seed-leaders`)
- Function: `def seed_creators(filepath):` (was `seed_leaders`)
- `async def _seed_creators(...)` (was `_seed_leaders`)
- `from sieve.db.models import Creator` (was `Leader`)
- `creator = Creator(...)` (was `leader = Leader(...)`)
- All user-facing strings: "leaders" → "creators"

**Step 7: Run quick sanity check**

Run: `uv run python -c "from sieve.api.app import app; print('Routes OK')"`
Expected: `Routes OK`

**Step 8: Commit**

```bash
git add -A
git commit -m "refactor: rename leader to creator in app, capture, dashboard, CLI"
```

---

### Task 4: Rename templates and CSS

**Files:**
- Rename: `src/sieve/dashboard/templates/leader.html` → `creator.html`
- Rename: `src/sieve/dashboard/templates/partials/leader_card.html` → `creator_card.html`
- Rename: `src/sieve/dashboard/templates/partials/leader_grid.html` → `creator_grid.html`
- Modify: `src/sieve/dashboard/templates/discover.html` — update HTMX endpoints and tab text
- Modify: `src/sieve/dashboard/static/style.css` — rename `.leader-*` → `.creator-*`

**Step 1: Rename template files**

```bash
mv src/sieve/dashboard/templates/leader.html src/sieve/dashboard/templates/creator.html
mv src/sieve/dashboard/templates/partials/leader_card.html src/sieve/dashboard/templates/partials/creator_card.html
mv src/sieve/dashboard/templates/partials/leader_grid.html src/sieve/dashboard/templates/partials/creator_grid.html
```

**Step 2: Update creator.html**

Global replace in file:
- `leader.` → `creator.` (template variables)
- `class="leader-` → `class="creator-`
- `hx-get="/htmx/leaders/` → `hx-get="/htmx/creators/`
- `id="leader-capsules"` → `id="creator-capsules"`

**Step 3: Update creator_card.html**

- `class="leader-card"` → `class="creator-card"`
- `class="leader-avatar"` etc. → `class="creator-avatar"` etc.
- `leader.` → `creator.` (all template variables)
- `href="/leader/{{ leader.slug }}"` → `href="/creator/{{ creator.slug }}"`

**Step 4: Update creator_grid.html**

- `{% if leaders %}` → `{% if creators %}`
- `{% for leader in leaders %}` → `{% for creator in creators %}`
- `{% include "partials/leader_card.html" %}` → `{% include "partials/creator_card.html" %}`
- `No leaders found` → `No creators found`

**Step 5: Update discover.html**

- `hx-get="/htmx/leaders/"` → `hx-get="/htmx/creators/"` (all occurrences)
- Tab label `>Leaders</button>` → `>Creators</button>`

**Step 6: Update style.css**

Global replace:
- `.leader-card` → `.creator-card`
- `.leader-avatar` → `.creator-avatar`
- `.leader-avatar--placeholder` → `.creator-avatar--placeholder`
- `.leader-stats` → `.creator-stats`
- `.leader-profile` → `.creator-profile`
- `.leader-header` → `.creator-header`
- `.leader-profile-avatar` → `.creator-profile-avatar`
- `.leader-info` → `.creator-info`
- `.leader-bio` → `.creator-bio`
- `.leader-links` → `.creator-links`
- `.leader-link` → `.creator-link`

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor: rename leader to creator in templates and CSS"
```

---

### Task 5: Rename extension code

**Files:**
- Rename: `extension/src/core/admin-leaders.ts` → `extension/src/core/admin-creators.ts`
- Modify: `extension/src/core/popup.ts` — update import path and references
- Modify: `extension/src/background.ts` — rename leader variables and comments
- Modify: `extension/src/utils/sieve-api-client.ts` — rename functions and endpoints
- Modify: `extension/src/popup.html` — rename element IDs and text

**Step 1: Rename the module file**

```bash
mv extension/src/core/admin-leaders.ts extension/src/core/admin-creators.ts
```

**Step 2: Update admin-creators.ts**

Global replacements:
- `leadersCache` → `creatorsCache`
- `listLeaders` → `listCreators`
- `createLeader` → `createCreator`
- `add-leader-section` → `add-creator-section`
- `leader-select` → `creator-select`
- `leader-domain` → `creator-domain`
- `add-leader-btn` → `add-creator-btn`
- `No leader` → `No creator`
- `Add as Leader` → `Add as Creator`
- `leader` variable names → `creator` (in loops, finds, etc.)
- `getSelectedLeaderId` → `getSelectedCreatorId`
- `populateLeaderSelect` → `populateCreatorSelect`
- `resetLeaderSelect` → `resetCreatorSelect`
- `autoSelectLeaderByTwitterUrl` → `autoSelectCreatorByTwitterUrl`
- `setupAddLeaderButton` → `setupAddCreatorButton`
- Comment text: "leader" → "creator"
- Error messages: "Failed to load leaders" → "Failed to load creators", "Failed to create leader" → "Failed to create creator"
- Description template: `"${domain} leader"` → `"${domain} creator"`

**Step 3: Update popup.ts**

- `import { initializeAdminSection, getSelectedCreatorId } from './admin-creators';` (was `admin-leaders`, `getSelectedLeaderId`)
- Comment: `// Initialize admin section (creators UI)` (was leaders)
- `leader_id?: string` → `creator_id?: string` in captureRequest type
- `captureRequest.leader_id` → `captureRequest.creator_id`
- `const selectedCreatorId = getSelectedCreatorId();` (was `selectedLeaderId`)
- `if (selectedCreatorId)` (was `selectedLeaderId`)

**Step 4: Update background.ts**

- Comment: `// Auto-assign creator by Twitter URL` (was leader)
- `let creator_id` (was `leader_id`)
- `const creators = await listCreators(...)` (was `listLeaders`)
- `leaders.find((leader: any)` → `creators.find((creator: any)`
- `leader.twitter_url` → `creator.twitter_url`
- `extractTwitterHandle(leader.twitter_url)` → `extractTwitterHandle(creator.twitter_url)`
- `if (match) creator_id = match.id`
- `body.creator_id` (was `body.leader_id`)
- Import: `listCreators` (was `listLeaders`)

**Step 5: Update sieve-api-client.ts**

- `CaptureRequest.leader_id` → `creator_id`
- `export async function createLeader(...)` → `createCreator(...)`
- Endpoint: `${serverUrl}/api/creators/` (was `/api/leaders/`)
- Error: `Failed to create creator` (was leader)
- `export async function listLeaders(...)` → `listCreators(...)`
- Endpoint: `${serverUrl}/api/creators/` (was `/api/leaders/`)
- `data.creators || []` (was `data.leaders`)

**Step 6: Update popup.html**

- `id="add-leader-section"` → `id="add-creator-section"`
- `id="leader-domain"` → `id="creator-domain"`
- `id="add-leader-btn"` → `id="add-creator-btn"`, text `Add as Creator`
- `id="capture-to-leader-section"` → `id="capture-to-creator-section"`
- `id="leader-select"` → `id="creator-select"`
- `— No leader —` → `— No creator —`
- Admin label can stay "Admin"

**Step 7: Build extension**

Run: `cd extension && npm run build`
Expected: Compiled with warnings (asset size only)

**Step 8: Commit**

```bash
git add -A
git commit -m "refactor: rename leader to creator in extension"
```

---

### Task 6: Add "Save to My Sieve" endpoint

**Files:**
- Modify: `src/sieve/api/capsules/routes.py` — add new POST endpoint
- Modify: `src/sieve/api/capsules/schemas.py` — add SaveCapsuleResponse if needed

**Step 1: Write the failing test**

Add to `tests/test_leaders.py` (which will be renamed in Task 7):

```python
async def test_save_creator_capsule_to_personal_sieve(client, admin_headers, user_headers, db_session):
    """User can copy a creator's capsule into their personal sieve."""
    # Create a creator
    creator_resp = await client.post("/api/creators/", json={
        "name": "Test Creator", "slug": "test-save", "description": "test"
    }, headers=admin_headers)
    creator_id = creator_resp.json()["id"]

    # Capture a capsule to the creator (admin)
    cap_resp = await client.post("/api/capture/", json={
        "content": "Some valuable insight about testing.",
        "creator_id": creator_id,
    }, headers=admin_headers)
    capsule_id = cap_resp.json()["id"]

    # User saves it to their personal sieve
    save_resp = await client.post(f"/api/capsules/{capsule_id}/save", headers=user_headers)
    assert save_resp.status_code == 201
    saved = save_resp.json()
    assert saved["id"] != capsule_id  # it's a copy
    assert saved["source_type"] == "creator_pack"
```

**Step 2: Implement the endpoint in `src/sieve/api/capsules/routes.py`**

```python
@router.post("/{capsule_id}/save", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
async def save_capsule_to_sieve(
    capsule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Copy a creator pack capsule into the user's personal sieve."""
    # Load original capsule (must be a creator pack capsule)
    result = await db.execute(select(Capsule).where(Capsule.id == capsule_id))
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Capsule not found")
    if not original.pack_id:
        raise HTTPException(status_code=400, detail="Can only save creator pack capsules")

    # Get user's sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(status_code=404, detail="Sieve not found")

    # Create copy
    copy = Capsule(
        sieve_id=sieve.id,
        pack_id=None,
        title=original.title,
        executive_summary=original.executive_summary,
        core_insight=original.core_insight,
        full_content=original.full_content,
        tags=original.tags,
        keywords=original.keywords,
        topics=original.topics,
        category=original.category,
        domain=original.domain,
        difficulty=original.difficulty,
        content_type=original.content_type,
        author=original.author,
        source_url=original.source_url,
        capture_method="saved",
        source_type="creator_pack",
    )
    db.add(copy)
    await db.commit()
    await db.refresh(copy)
    return capsule_to_response(copy)
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -v -x`
Expected: All pass

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: add POST /api/capsules/{id}/save endpoint for copying creator capsules"
```

---

### Task 7: Rename tests and seed data

**Files:**
- Rename: `tests/test_leaders.py` → `tests/test_creators.py`
- Modify: all references inside the test file
- Modify: `data/leaders-seed.json` → `data/creators-seed.json`

**Step 1: Rename test file**

```bash
mv tests/test_leaders.py tests/test_creators.py
```

**Step 2: Global replace in test_creators.py**

- `leader` → `creator` (variable names, function names, URLs)
- `Leader` → `Creator` (model references)
- `/api/leaders/` → `/api/creators/`
- `leader_id` → `creator_id`
- `leaders` → `creators` (in response field checks)
- Test function names: `test_create_leader` → `test_create_creator`, etc.

**Step 3: Rename seed data**

```bash
mv data/leaders-seed.json data/creators-seed.json
```

**Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All pass

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename leader to creator in tests and seed data"
```

---

### Task 8: Update documentation

**Files:**
- Modify: `DEPLOYMENT.md` — update all leader references

**Step 1: Update DEPLOYMENT.md**

- "leader packs" → "creator packs"
- "Leaders" → "Creators" (in Discover page description)
- `seed-leaders` → `seed-creators` if referenced

**Step 2: Commit**

```bash
git add DEPLOYMENT.md
git commit -m "docs: rename leader to creator in deployment guide"
```

---

### Task 9: Final verification

**Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All pass

**Step 2: Run migration check**

Run: `uv run alembic current`
Expected: `005`

**Step 3: Build extension**

Run: `cd extension && npm run build`
Expected: Compiled with no errors (warnings OK)

**Step 4: Grep for remaining "leader" references (excluding docs/plans, migrations, node_modules)**

Run: `grep -r "leader" src/ extension/src/ tests/ --include="*.py" --include="*.ts" --include="*.html" --include="*.css" --include="*.json" -l | grep -v node_modules | grep -v docs/plans | grep -v migrations/versions`
Expected: No files found (or only the seed JSON if not renamed yet)

**Step 5: Start server and smoke test**

Run: `uv run sieve serve`
- Visit `/creators/` page
- Visit `/discover` — tab should say "Creators"
- Test capture with creator selected
- Test capture without creator (personal sieve)
