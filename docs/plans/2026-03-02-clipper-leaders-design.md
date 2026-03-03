# Sieve Clipper + Leaders System — Design

**Status:** Approved (Updated 2026-03-03)
**Date:** 2026-03-02

## Goal

Build a curated library of ~100 thought leaders (Karpathy, Cursor team, Perplexity, etc.) organized by expertise domain, each with 5-10 manually seeded capsules of their best insights from Twitter and long-form content. Users browse leaders by domain, read their capsules, and compile them into Claude Code skills.

The Sieve Clipper browser extension is the primary tool for both capturing content AND populating the leader database.

## Current State (as of 2026-03-03)

### Phase 1: Sieve Clipper — COMPLETE

The extension is built and deployed (v1.0.2). All user-facing capture features work:
- One-click capture of any web page via `POST /api/capture/`
- Email/password + Google OAuth login in popup
- JWT token storage in `browser.storage.sync`
- Toast notifications ("Saved to your Sieve")
- Context menu capture (page or selection)
- Side panel, highlighter, reader mode
- Keyboard shortcuts (Ctrl+Shift+O quick clip, etc.)

**What's NOT yet built in the extension:**
- Admin-only "Add as Leader" UI for Twitter profiles
- "Capture to Leader" mode (linking captures to a specific leader)
- Twitter DOM extraction (auto-extract name, bio, avatar from profile pages)
- `is_admin` check on JWT to show/hide admin features

### Other Completed Systems

- Dashboard (warm cream theme, 10+ pages, HTMX-driven)
- Social network (Follow model, feed, discover, profiles, follow/unfollow)
- Skills (CRUD, compile, export to `.claude/skills/`, MCP access)
- Auth (email/password + Google OAuth, JWT cookies)
- MCP server (6 tools: search_capsules, get_capsule, get_pinned, get_index, search_skills, get_skill)
- Vault import (basic ZIP upload + markdown parsing)

---

## What Remains to Build

### 1. Leaders Backend (evolve LeaderPack → Leader)

Evolve `LeaderPack` → `Leader` by renaming the table and adding profile fields. Keep existing `Capsule.pack_id` FK. Subscription and Review models stay unchanged.

**New columns on Leader (formerly leader_packs):**

| Column | Type | Note |
|--------|------|------|
| `avatar_url` | String(2000) | NEW — profile image URL |
| `bio` | String(500) | NEW — short bio |
| `expertise_domain` | String(100) | NEW — "AI/ML", "Developer Tools", etc. |
| `twitter_url` | String(500) | NEW — X/Twitter profile URL |
| `linkedin_url` | String(500) | NEW — LinkedIn profile URL |
| `is_featured` | Boolean | NEW — admin toggle for promoted leaders |
| `capsule_count` | Integer | NEW — denormalized count for display |

**Kept from LeaderPack:** id, name, slug, description, author_url, version, topics[], rating_avg, review_count, created_at.

**Expertise domains (predefined):**
- AI/ML
- Developer Tools
- Search & Retrieval
- Startups & Indie Hacking
- Product & Design
- Engineering Leadership
- Open Source
- Security
- Data & Infrastructure

**API endpoints:**

```
GET    /api/leaders/                    → list leaders (public, supports ?domain= filter)
GET    /api/leaders/{slug}              → get leader profile (public)
GET    /api/leaders/{slug}/capsules     → list capsules for a leader (public)
POST   /api/leaders/                    → create leader (admin only)
PUT    /api/leaders/{slug}              → update leader (admin only)
DELETE /api/leaders/{slug}              → delete leader (admin only)
```

**Capture extension:**

```
POST   /api/capture/                    → existing endpoint, add optional leader_id param
```

**Migration:** Alembic migration to rename `leader_packs` → `leaders`, add new columns, update FK constraints.

### 2. Leaders Dashboard (Discover page rework)

**`/discover` — add Leaders tab:**

The discover page already has sieves and capsules tabs. Add a "Leaders" tab (or make leaders the primary view).

```
┌─────────────────────────────────────────────────┐
│  Discover                                        │
│  [Leaders] [Sieves] [Capsules]                   │
│                                                  │
│  [All] [AI/ML] [Dev Tools] [Search] [Startups]   │  ← domain filter
│                                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │  avatar      │ │  avatar      │ │  avatar     │ │
│  │ Karpathy    │ │ Aman Sanger │ │ Aravind S. │ │
│  │ AI/ML       │ │ Dev Tools   │ │ Search     │ │
│  │ "Former..." │ │ "CEO of..." │ │ "CEO of..." │ │
│  │ 12 capsules │ │ 8 capsules  │ │ 10 capsules│ │
│  │ [View →]    │ │ [View →]    │ │ [View →]   │ │
│  └─────────────┘ └─────────────┘ └────────────┘ │
└─────────────────────────────────────────────────┘
```

**`/leader/{slug}` — Leader Profile page (NEW):**

- Header: avatar, name, bio, social links, expertise domain badge
- Grid of their capsules (same card layout as My Sieve)
- Subscribe button (wired up via existing Subscription model)

**HTMX endpoints:**

```
GET  /htmx/leaders/                     → leader card grid (supports ?domain= filter)
GET  /htmx/leaders/{slug}/capsules/     → capsule grid for a leader
```

### 3. Extension Admin Features

Add admin-only UI to the existing Clipper extension:

**Twitter profile detection + "Add as Leader":**
- Content script detects `x.com/{handle}` pages
- Extracts: display name, bio, avatar URL, handle, website from DOM
- Popup shows "Add as Leader" button + domain dropdown (admin only)
- Sends `POST /api/leaders/` with extracted data

**"Capture to Leader" mode:**
- On any page, admin can select a leader from a dropdown
- Capture links the capsule to that leader via `leader_id`
- Dropdown populated by `GET /api/leaders/` (cached)

**Admin gating:**
- JWT `is_admin` claim controls visibility
- Auth storage already includes token — just decode and check

### 4. Admin CLI (fallback)

`uv run sieve seed-leaders --file leaders.yaml` — bulk import for when using the extension one-by-one is impractical.

---

## Admin Workflow (How to Populate 100 Leaders)

1. Log into the Sieve Clipper as admin
2. Browse to `x.com/karpathy` → extension detects Twitter profile
3. Click "Add as Leader" → name, bio, avatar auto-extracted
4. Select "AI/ML" as expertise domain → click submit
5. Scroll through Karpathy's best tweets/threads
6. Click "Capture to Leader" on each great piece → capsules created and linked
7. Repeat for all 100 leaders
8. Users see the populated `/discover` page with Leaders tab

---

## What's NOT in This Design

- No automated scraping (future phase)
- No user-submitted leaders (future — admin-only for now)
- No comments, likes, or social interactions on leaders
- No subscription notifications
- No semantic/vector search on leader capsules
- No LinkedIn scraping (manual entry only for LinkedIn URLs)
