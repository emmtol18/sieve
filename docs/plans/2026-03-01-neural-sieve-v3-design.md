# Neural Sieve v3 — Design Document

**Date:** 2026-03-01
**Status:** Draft
**Author:** Lucas Fischer + Claude

---

## Vision

Neural Sieve v3 is an **Obsidian-powered, cloud-first knowledge-to-skills pipeline** that turns captured knowledge into active AI capabilities.

Users capture insights from the web (via Obsidian Clipper + Obsidian plugin), curate and discover thought leader knowledge packs, and compile everything into Claude Code skills and MCP-searchable knowledge — available from any device, always on.

**Three value propositions:**

1. **Personal capture** — clip from the web, LLM extracts structured capsules, searchable by your AI agents
2. **Leader packs** — curated knowledge from power users (Karpathy, Levelsio, etc.) distributed as subscribable packs with ratings
3. **Skills at load time** — capsule knowledge compiled into Claude Code skills that load at session start, plus MCP search for deeper queries

---

## Target Users

- **Power users:** Developers who use Obsidian + Claude Code. They capture knowledge, sync locally, and want maximum control.
- **Non-technical users:** People who want curated AI knowledge without touching git or config files. They use the web dashboard and phone.

Both served equally from day one.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      CAPTURE LAYER                        │
│                                                          │
│  Stock Obsidian Clipper ──→ Obsidian Vault (Inbox/)      │
│                                    ↓                     │
│                     Sieve Obsidian Plugin (TypeScript)    │
│                     - Watches Inbox/ for new clips        │
│                     - Calls LLM to extract capsule        │
│                     - Writes structured capsule .md       │
│                                                          │
│  Web Dashboard ──→ Cloud API (non-tech / phone capture)  │
│  Chrome Ext ────→ Cloud API (quick browser capture)      │
└──────────────┬───────────────────────┬───────────────────┘
               │                       │
┌──────────────▼───────────────────────▼───────────────────┐
│              CLOUD BACKEND (always-on)                    │
│              FastAPI + PostgreSQL                         │
│                                                          │
│  - Source of truth for all capsules                      │
│  - LLM processing (clip → capsule extraction)            │
│  - Semantic search index                                 │
│  - User accounts (email/password)                        │
│  - Leader pack library (browse, subscribe, rate)         │
│  - API for MCP server + dashboard + mobile               │
│                                                          │
│  ←→ Obsidian Vault Sync (optional, for power users)      │
└──────┬────────────────┬────────────────┬─────────────────┘
       │                │                │
┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────────────┐
│ MCP SERVER  │  │   SKILL     │  │  WEB DASHBOARD      │
│ (Python)    │  │  COMPILER   │  │  (PWA)              │
│             │  │  (Python)   │  │                     │
│ Connects to │  │             │  │  Responsive         │
│ cloud API   │  │ Cloud API → │  │  Phone + desktop    │
│             │  │ .claude/    │  │  Browse, capture,   │
│ Always has  │  │ skills/     │  │  manage, compile    │
│ latest data │  │             │  │                     │
│             │  │ `sieve      │  │  FastAPI + HTMX     │
│ `sieve mcp` │  │  compile`   │  │  + Jinja2           │
└─────────────┘  └─────────────┘  └─────────────────────┘
```

**Design principle:** Cloud backend is the source of truth. Obsidian vault sync is an optional power-user feature. MCP server connects to cloud API so knowledge is always accessible from any machine.

---

## Component Details

### 1. Capsule Format

Each capsule is an Obsidian-compatible markdown file with rich metadata for discovery.

```yaml
---
id: "2026-03-01-T100000"
title: "Karpathy: LLMs Are the New Operating System"
source_url: "https://twitter.com/karpathy/..."

# Discovery metadata (rich tagging for search)
tags: [llm, agents, os-analogy, architecture, ai-infrastructure]
category: "AI Architecture"
keywords: [operating-system, llm-runtime, tool-use, memory, context-window]
topics: [artificial-intelligence, software-architecture, future-of-computing]
domain: "technology"
difficulty: "intermediate"        # beginner, intermediate, advanced
content_type: "insight"           # insight, tutorial, opinion, research, case-study

# Provenance
author: "personal"                # or "karpathy", "levelsio", etc.
pack: null                        # or "karpathy-pack-v1"
captured_at: "2026-03-01"
capture_method: "clipper"         # clipper, manual, import, phone, dashboard
source_type: "twitter"            # twitter, blog, video, paper, book, podcast

# System
status: active
pinned: false
skill_eligible: true
---

## Executive Summary
2-sentence hook for AI comprehension.

## Core Insight
The main takeaway — what makes this knowledge actionable.

## Full Content
Complete cleaned text from the source.

## Connections
- [[related-capsule-1]]
- [[related-capsule-2]]
```

**Discovery axes:** tags (5-10 specific), keywords (semantic search terms), topics (broad themes), domain, difficulty, content_type, source_type. Multiple paths to the same knowledge.

**Obsidian compatibility:** Valid markdown with YAML frontmatter and `[[wiki-links]]`. Browsable in Obsidian graph view, searchable, editable.

---

### 2. Leader Packs

A leader pack is a curated collection of capsules from a thought leader, packaged for distribution.

**Structure:**
```
leader-packs/
  karpathy/
    manifest.yaml
    capsules/
      llm-os.md
      software-2-0.md
      recipe-for-training.md
    skills/                      # pre-compiled Claude skills
      karpathy-ai-principles.md
      karpathy-training-guide.md
    README.md
```

**manifest.yaml:**
```yaml
name: "Andrej Karpathy"
slug: "karpathy"
version: "1.0.0"
description: "AI/ML insights from Karpathy's talks, blogs, and tweets"
author_url: "https://karpathy.ai"
capsule_count: 25
topics: [ai, ml, training, agents, software-2-0]
last_updated: "2026-03-01"
rating: 4.8                      # community rating
review_count: 142
```

**Distribution model:**
- Browse pack library in web dashboard
- One-click subscribe → capsules sync to user's sieve
- Pre-compiled skills injected into user's `.claude/skills/`
- Updates pushed when new capsules are curated
- Rating/review system so best packs surface

**Curation:**
- Initial packs curated by Neural Sieve team
- Power users can submit their own public sieves as packs
- Quality gate: packs reviewed before listing

**Starter packs (Phase 1):**
- Andrej Karpathy — AI/ML, training, agents, software 2.0
- Pieter Levels (Levelsio) — shipping fast, solo founder, bootstrapping
- Boris Cherny — Claude Code workflows, agent development
- Patrick Collison — scaling, hiring, technology strategy

---

### 3. Sieve Obsidian Plugin (TypeScript)

An Obsidian community plugin that processes raw clips into structured capsules.

**Functionality:**
- Watches `Inbox/` folder for new files (from Obsidian Clipper)
- Sends content to LLM (via cloud API) for capsule extraction
- Writes structured capsule `.md` to `Capsules/<category>/`
- Updates `INDEX.md`
- Syncs capsules bidirectionally with cloud backend
- Settings panel: API key, LLM model, processing preferences

**UI in Obsidian:**
- Status bar: "Sieve: 3 clips processing..."
- Ribbon icon for manual capture
- Settings tab for configuration
- Command palette: "Process clip", "Sync with cloud", "Compile skills"

**Built using:** `obsidian-sample-plugin` template, TypeScript, esbuild.

---

### 4. Cloud Backend (Python/FastAPI)

The always-on source of truth.

**Tech stack:**
- Python 3.12+, FastAPI, SQLAlchemy async + asyncpg
- PostgreSQL 16
- LLM: OpenAI API (or configurable)
- Hosted on Fly.io (or Railway/Render)

**API endpoints:**

```
# Auth
POST   /auth/register
POST   /auth/login
GET    /auth/me

# Capsules
GET    /capsules                  # list with filters
POST   /capsules                  # create (raw content → LLM → capsule)
GET    /capsules/{id}
PUT    /capsules/{id}
DELETE /capsules/{id}
POST   /capsules/search           # semantic search

# Leader Packs
GET    /packs                     # browse library
GET    /packs/{slug}              # pack detail
POST   /packs/{slug}/subscribe
DELETE /packs/{slug}/unsubscribe
POST   /packs/{slug}/rate
GET    /packs/{slug}/reviews

# Sync
POST   /sync/push                 # push local changes
POST   /sync/pull                 # pull remote changes
GET    /sync/status

# Skills
POST   /skills/compile            # trigger compilation
GET    /skills                    # list generated skills
GET    /skills/{id}/download      # download skill file
```

**Data model (PostgreSQL):**

```
users
  id, email, password_hash, created_at

sieves (1:1 with users)
  id, user_id, name

capsules
  id, sieve_id, title, content, frontmatter (JSONB),
  embedding (vector), created_at, updated_at

leader_packs
  id, name, slug, description, author_url,
  version, topics, rating_avg, review_count

pack_capsules
  id, pack_id, capsule content...

subscriptions
  user_id, pack_id, subscribed_at

reviews
  user_id, pack_id, rating, comment, created_at

compiled_skills
  id, user_id, name, content, source_pack_id, compiled_at
```

---

### 5. Skill Compiler (Python CLI)

Transforms capsules into Claude Code skill files.

**Usage:**
```bash
sieve compile --pack karpathy       # one leader pack → skill
sieve compile --personal            # personal capsules → skill
sieve compile --all                 # everything → skills
sieve compile --project ./my-app    # project-relevant capsules → skills
```

**Process:**
1. Fetches capsules from cloud API (filtered by pack/personal/all)
2. Groups by author, topic, or relevance
3. Sends to LLM with summarization prompt: "Distill these N capsules into a concise Claude skill file with principles, patterns, and heuristics"
4. Outputs `.claude/skills/<name>.md` files
5. Pinned capsules → injected into `CLAUDE.md`

**Generated skill format:**
```markdown
---
name: karpathy-ai-principles
description: AI development principles from Andrej Karpathy
---

## Core Principles
1. Start simple, add complexity only when needed
2. Always have a baseline to compare against
3. Never trust your data pipeline...

## When Training Models
- Always visualize your data first...
- Use a simple model as baseline...

## When Building Agents
- LLMs are the new OS kernel...
- Keep tool interfaces simple...
```

---

### 6. MCP Server (Python)

Evolves v1's MCP server to connect to the cloud API.

**Tools exposed:**
- `search_capsules(query, filters)` — semantic search with rich filtering (tags, domain, difficulty, author, pack)
- `get_capsule(id)` — fetch specific capsule
- `get_pinned()` — user's pinned "eternal truths"
- `get_index()` — full knowledge index
- `get_pack_summary(pack)` — leader pack overview
- `suggest_relevant(context)` — given current coding context, suggest relevant capsules

**Connection:** Authenticates to cloud API with user's API key. Always has latest data regardless of which machine Claude Code runs on.

**Config:**
```json
{
  "mcpServers": {
    "neural-sieve": {
      "command": "sieve",
      "args": ["mcp"],
      "env": {
        "SIEVE_API_KEY": "sk-..."
      }
    }
  }
}
```

---

### 7. Web Dashboard (PWA)

Responsive web application for phone + desktop access.

**Tech:** FastAPI + HTMX + Jinja2, responsive CSS, PWA manifest.

**Pages:**

| Page | Purpose |
|------|---------|
| **My Sieve** | Browse, search, edit, pin capsules. Filter by tags/domain/difficulty. |
| **Discover** | Browse leader pack library. Ratings, reviews, subscribe. |
| **Capture** | Quick capture form — paste URL or text, phone-friendly. |
| **Compile** | Trigger skill compilation, preview generated skills, download. |
| **Settings** | Account, API key, Obsidian sync config, notification preferences. |

**PWA features:** Installable on phone home screen, offline capsule browsing (cached), push notifications for new pack updates.

---

## Sync Architecture

**Cloud ↔ Obsidian vault sync (optional, for power users):**

```
Obsidian Vault                  Cloud Backend
    │                               │
    ├── Capsules/                   ├── capsules table
    │   ├── tech/note.md  ←────→   │   row (id, content, frontmatter)
    │   └── ...                     │
    ├── Inbox/     ──────→          ├── processing queue
    └── INDEX.md   ←──────          └── auto-generated
```

- Sieve Obsidian Plugin handles sync
- Conflict resolution: last-write-wins with merge for non-overlapping edits
- Sync triggered on: file change (debounced), app open, manual trigger

---

## Tech Stack Summary

| Component | Language | Framework | Notes |
|-----------|----------|-----------|-------|
| Cloud backend | Python 3.12 | FastAPI + SQLAlchemy | Reuses v1/v2 patterns |
| Database | — | PostgreSQL 16 | + pgvector for embeddings |
| Dashboard | Python + HTML | HTMX + Jinja2 | Server-rendered, responsive |
| MCP server | Python | MCP SDK | Reuses v1 architecture |
| Skill compiler | Python | CLI (click/typer) | New component |
| Obsidian plugin | TypeScript | Obsidian API | New component |
| Chrome extension | TypeScript | Manifest V3 | Reuses v1 extension |
| Hosting | — | Fly.io | Docker + PostgreSQL |
| LLM | — | OpenAI API | Capsule extraction + search ranking |

---

## Phase Plan

### Phase 1: Core Pipeline (MVP)
- Cloud backend with auth + capsule CRUD + search
- Skill compiler CLI
- MCP server (cloud-connected)
- Basic web dashboard (My Sieve + Capture)
- Migrate v1 capsules

### Phase 2: Leader Packs
- Pack data model + API
- Discover page in dashboard
- First 3-4 curated packs (Karpathy, Levelsio, etc.)
- Subscribe/unsubscribe flow
- Rating system

### Phase 3: Obsidian Integration
- Sieve Obsidian Plugin (clip processing + sync)
- Bidirectional vault sync
- Obsidian community plugin submission

### Phase 4: Mobile + Polish
- PWA enhancements (offline, push notifications)
- Phone-optimized capture
- Advanced search filters
- Pack submission by power users

---

## Success Criteria

1. Personal capsules are always accessible to Claude Code via MCP, from any machine
2. Users can subscribe to leader packs and have that knowledge active in their coding sessions
3. `sieve compile` generates useful Claude skills from capsule collections
4. Non-technical users can capture and browse knowledge from their phone
5. Power users can optionally sync with Obsidian for local editing and graph visualization

---

## Reference Repositories

Cloned to `/Users/lucasfischer/Documents/Code/neural-sieve-v3-research/`:

| Repo | Use |
|------|-----|
| `obsidian-clipper` | Reference for web clipping pipeline (turndown, defuddle) |
| `obsidian-api` | TypeScript types for plugin development |
| `obsidian-importer` | Import logic for multiple formats |
| `obsidian-sample-plugin` | Plugin development template |
| `jsoncanvas` | Canvas format spec (future: visual knowledge maps) |
| `obsidian-headless` | CLI sync without desktop app |

Existing codebases:
| Codebase | Path | Reuse |
|----------|------|-------|
| Neural Sieve v1 | `/Users/lucasfischer/Documents/Code/sieve_ideas/neural-sieve/` | MCP server, capsule schema, processing engine |
| Neural Sieve v2 | `/Users/lucasfischer/Documents/Code/neural-sieve-v2/` | Cloud backend design, FastAPI patterns, auth |
