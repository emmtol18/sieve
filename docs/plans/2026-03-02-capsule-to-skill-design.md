# Capsule-to-Skill Feature Design

**Date**: 2026-03-02
**Status**: Approved

## Overview

Allow users to create persistent skills from capsules, managed through a new Skills page in the dashboard. Skills are stored in the database, editable, exportable as `.claude/skills/*.md` files, and accessible via MCP.

## Data Model

### Skill Table

| Column       | Type           | Notes                                      |
|-------------|----------------|---------------------------------------------|
| `id`        | UUID (PK)      |                                             |
| `sieve_id`  | FK → Sieve     | Owner's sieve                               |
| `name`      | String(200)    | Skill identifier (slugified, e.g. `sieve-deep-work`) |
| `title`     | String(500)    | Human-readable display name                 |
| `description` | String(2000) | "Use when..." triggering text               |
| `body`      | Text           | Full markdown skill content                 |
| `status`    | String(50)     | `active` / `archived`, default `active`     |
| `created_at` | DateTime(tz)  | Auto-set                                    |
| `updated_at` | DateTime(tz)  | Auto-updated                                |

### SkillCapsule Association Table (many-to-many)

| Column       | Type           | Notes                                      |
|-------------|----------------|---------------------------------------------|
| `skill_id`  | FK → Skill (PK) |                                           |
| `capsule_id` | FK → Capsule (PK) |                                        |
| `role`      | String(50)     | `primary` or `context`                      |

A skill tracks all capsules that went into creating it. The `primary` capsule is the main source; `context` capsules provide enriching material for the LLM compilation.

## User Flows

### Flow A: Create Skill from Capsule Detail

1. User views capsule at `/capsule/{id}`
2. Clicks **"Create Skill"** button (alongside Edit/Pin/Delete actions)
3. An expandable section or modal appears showing:
   - Current capsule as the "primary" source (read-only)
   - Searchable dropdown to optionally add more capsules as context
   - "Compile" button
4. HTMX POST to `/htmx/skills/compile` with capsule IDs and roles
5. LLM compiler generates skill name, description, and body
6. Skill saved to DB, user redirected to skill detail page

### Flow B: Skills Page (`/skills`)

- New page in the main navigation
- Grid layout matching the sieve page aesthetic (dark theme, cards)
- Each card shows: skill title, description excerpt, source capsule count, created date
- Click card → skill detail page `/skills/{id}`
- Search bar to filter by name/description

### Flow C: Skill Detail Page (`/skills/{id}`)

- Displays: title, description, full body (rendered markdown), list of source capsules
- **Edit**: Inline editing of title, description, and body via HTMX PUT
- **Export**: Button writes `.md` file to `.claude/skills/` directory, shows confirmation
- **Delete**: With confirmation dialog, HTMX DELETE
- **Re-compile**: Button to regenerate body from linked capsules (useful if capsules were updated)

### Flow D: Navigation

Add **"Skills"** to the main nav bar. Keep the existing Compile page for batch operations.

## Compiler Changes

Adapt `SkillCompiler` to:

1. **Return structured data** (name, description, body) as a Pydantic model instead of only writing files to disk
2. **Accept capsules with roles** — primary capsule provides main content, context capsules enrich the prompt
3. **Updated LLM prompt** for multi-capsule input with role awareness:
   - Primary capsule content presented as the main source
   - Context capsules presented as supporting material

Existing batch compile flow (`/compile` page) remains unchanged.

## API Endpoints

### REST API (`/api/skills/`)

| Method   | Path                         | Purpose                                |
|----------|------------------------------|----------------------------------------|
| `POST`   | `/api/skills/compile`        | Compile capsule(s) into a new skill    |
| `GET`    | `/api/skills/`               | List user's skills (search, pagination)|
| `GET`    | `/api/skills/{id}`           | Get skill detail                       |
| `PUT`    | `/api/skills/{id}`           | Update skill (title, description, body)|
| `DELETE` | `/api/skills/{id}`           | Delete skill                           |
| `POST`   | `/api/skills/{id}/export`    | Write skill as .md to `.claude/skills/`|
| `POST`   | `/api/skills/{id}/recompile` | Re-generate body from linked capsules  |

### HTMX Routes (`/htmx/skills/`)

Mirror the REST endpoints for dashboard interactivity:

| Method   | Path                              | Returns              |
|----------|-----------------------------------|----------------------|
| `POST`   | `/htmx/skills/compile`           | Redirect to detail   |
| `GET`    | `/htmx/skills/`                  | Skill grid partial   |
| `PUT`    | `/htmx/skills/{id}`              | Updated detail view  |
| `DELETE` | `/htmx/skills/{id}`              | Empty (remove card)  |
| `POST`   | `/htmx/skills/{id}/export`       | Success message      |
| `POST`   | `/htmx/skills/{id}/recompile`    | Updated body partial |

## MCP Integration

Add two tools to the MCP server:

### `search_skills`
- **Input**: `query` (required), `limit` (optional, default 10)
- **Output**: Formatted list of matching skills with name, description, and ID
- **Implementation**: Calls `/api/skills/?q={query}`

### `get_skill`
- **Input**: `id` (required)
- **Output**: Full skill content formatted as SKILL.md-compatible markdown (with YAML frontmatter)
- **Implementation**: Calls `/api/skills/{id}`

## Templates

### New Templates
- `skills.html` — Skills grid page (similar to `sieve.html`)
- `skill_detail.html` — Skill detail/edit page
- `partials/skill_card.html` — Card component for grid display
- `partials/skill_grid.html` — Grid container with card iteration
- `partials/compile_skill_form.html` — Capsule selector + compile button (used in capsule detail)

### Modified Templates
- `base.html` — Add "Skills" nav link
- `capsule_detail.html` — Add "Create Skill" button/section

## Pydantic Schemas

```python
class SkillCompileRequest(BaseModel):
    primary_capsule_id: UUID
    context_capsule_ids: list[UUID] = []

class SkillUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    body: str | None = None

class SkillResponse(BaseModel):
    id: UUID
    name: str
    title: str
    description: str
    body: str
    status: str
    source_capsules: list[CapsuleResponse]
    created_at: datetime
    updated_at: datetime

class SkillListResponse(BaseModel):
    skills: list[SkillResponse]
    total: int
```

## Export Format

When exported, skills are written as:

```markdown
---
name: sieve-{slug}
description: Use when...
---

{body}
```

File path: `.claude/skills/sieve-{slug}.md`

## Migration

Single Alembic migration adding:
- `skills` table
- `skill_capsules` association table
- Index on `skills.sieve_id`
- Index on `skills.name`
