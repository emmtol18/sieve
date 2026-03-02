# Sieve Clipper + Leaders System — Design

**Status:** Approved
**Date:** 2026-03-02

## Goal

Build a curated library of ~100 thought leaders (Karpathy, Cursor team, Perplexity, etc.) organized by expertise domain, each with 5-10 manually seeded capsules of their best insights from Twitter and long-form content. Users browse leaders by domain, read their capsules, and compile them into Claude Code skills.

The Sieve Clipper browser extension is the primary tool for both capturing content AND populating the leader database.

## Approach

- **Hybrid ingestion:** Manual curation first (admin seeds leaders + their best content via the Clipper), automated scraping later.
- **Content types:** Both short-form (tweets, threads) and long-form (blogs, Substacks).
- **Leader curation is admin-only.** Regular users browse and consume leader content. Adding/editing leaders requires `is_admin=True`.
- **Leaders organized by expertise domain:** AI/ML, Developer Tools, Search & Retrieval, Startups & Indie Hacking, Product & Design, Engineering Leadership, Open Source, Security, Data & Infrastructure.
- **Centrally curated initially** by the admin. Later phases open it to user submissions.

## Build Order

**Phase 1: Sieve Clipper** (browser extension) — the tool for populating everything.
**Phase 2: Leaders System** (backend + dashboard) — the data model and UI.

---

## Phase 1: Sieve Clipper (Browser Extension)

### Overview

Chrome extension forked from [Obsidian Web Clipper](https://github.com/obsidianmd/obsidian-clipper) (MIT license). Manifest V3, vanilla JS.

Single extension for all users. Admin-only features (leader management) are hidden behind an `is_admin` check on the user's JWT.

### Features

**For all users:**
- One-click capture of any web page → `POST /api/capture/` → creates a capsule
- Auth via extension popup (email/password or Google OAuth)
- Toast notification: "Captured: [title]"

**For admins only (hidden when `is_admin=false`):**
- **Add as Leader** — When on a Twitter profile (`x.com/{handle}`), auto-extracts name, bio, avatar URL, handle, website from the page DOM. Admin selects expertise domain from a dropdown. Sends `POST /api/leaders/`.
- **Capture to Leader** — When viewing a tweet or article, links the captured capsule to a specific leader. Admin picks the leader from a dropdown of existing leaders. Sends `POST /api/capture/` with `leader_id`.

### Extension Popup UI

```
┌──────────────────────────┐
│  Neural Sieve Clipper     │
│                           │
│  [Capture This Page]      │  ← always visible
│                           │
│  ─── Admin ────────────── │  ← only if is_admin
│                           │
│  [Add as Leader]          │  ← on Twitter profiles
│  Domain: [AI/ML      ▾]  │
│                           │
│  Leader: [Karpathy   ▾]  │  ← on any page
│  [Capture to Leader]      │
│                           │
│  ─────────────────────── │
│  lucas@...  [Logout]      │
└──────────────────────────┘
```

### Twitter DOM Extraction

When the extension detects a Twitter profile page (`x.com/{handle}`):

- **Name:** Display name from profile header
- **Bio:** Profile bio text
- **Avatar:** Profile image `src` attribute (high-res variant)
- **Handle:** From the URL or `@handle` element
- **Website:** Link from the profile's website field
- **Location:** Profile location (optional, stored as metadata)

Twitter posts are extracted as:
- **Content:** Tweet text (full thread if it's a thread)
- **Source URL:** Permalink to the tweet
- **Source type:** `tweet` or `thread`
- **Author:** Linked to the leader's handle

### Auth Flow

1. User clicks extension icon → popup opens
2. If not logged in: shows email/password form or "Sign in with Google" button
3. Extension stores JWT in `chrome.storage.local`
4. JWT includes `is_admin` claim → extension shows/hides admin features
5. All API calls include `Authorization: Bearer <token>` header

### Tech Stack

- Manifest V3 (Chrome Extension)
- Vanilla JS (no framework — keep it simple and fast)
- `chrome.storage.local` for auth token
- `content_script` for DOM extraction on Twitter pages
- `popup.html` for the UI
- Communicates with Neural Sieve API (`/api/capture/`, `/api/leaders/`)

---

## Phase 2: Leaders System (Backend + Dashboard)

### Data Model

Evolve `LeaderPack` → `Leader` by renaming the table and adding profile fields. Keep existing `Capsule.pack_id` FK (still points to the same table). Subscription and Review models stay unchanged.

**New/changed columns on Leader (formerly leader_packs):**

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

### API Endpoints

**Leader CRUD (admin-only for mutations):**

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

### Dashboard Pages

**`/discover` — Leaders Directory (reworked):**

```
┌─────────────────────────────────────────────────┐
│  Discover Leaders                                │
│  "Learn from the best minds in tech"             │
│                                                  │
│  [All] [AI/ML] [Dev Tools] [Search] [Startups]   │
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

**`/leader/{slug}` — Leader Profile:**

- Header: avatar, name, bio, social links, expertise domain badge
- Grid of their capsules (same card layout as My Sieve)
- Subscribe button (wired up for future use)

**HTMX endpoints:**

```
GET  /htmx/leaders/                     → leader card grid (supports ?domain= filter)
GET  /htmx/leaders/{slug}/capsules/     → capsule grid for a leader
```

### Admin CLI (fallback)

`uv run sieve seed-leaders --file leaders.yaml` — bulk import from YAML for cases where using the Clipper one-by-one is impractical.

### Migration

Alembic migration to:
1. Rename `leader_packs` → `leaders` table
2. Add new columns (avatar_url, bio, expertise_domain, twitter_url, linkedin_url, is_featured, capsule_count)
3. Update FK references if table name changes affect constraints

---

## Admin Workflow (How You'll Populate 100 Leaders)

1. Install the Sieve Clipper in Chrome, log in as admin
2. Browse to `x.com/karpathy` → extension detects Twitter profile
3. Click "Add as Leader" → name, bio, avatar auto-extracted
4. Select "AI/ML" as expertise domain → click submit
5. Scroll through Karpathy's best tweets/threads
6. Click "Capture to Leader" on each great piece → capsules created and linked
7. Repeat for all 100 leaders
8. Users see the populated `/discover` page

---

## What's NOT in This Design

- No automated scraping (future phase)
- No user-submitted leaders (future — admin-only for now)
- No comments, likes, or social interactions on leaders
- No subscription notifications
- No semantic/vector search on leader capsules
- No LinkedIn scraping (manual entry only for LinkedIn URLs)
