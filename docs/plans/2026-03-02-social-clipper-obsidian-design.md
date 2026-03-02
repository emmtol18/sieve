# Neural Sieve: Social Network + Sieve Clipper + Obsidian Import

**Date:** 2026-03-02
**Status:** Approved

## Vision

Transform Neural Sieve from a personal knowledge tool into a B2C knowledge-sharing social network with zero-friction capture. Obsidian users are first-class citizens. No CLI required — everything works from the browser.

Three pillars:
1. **Sieve Clipper** — Forked Obsidian Web Clipper, one-click capture, LLM does all the work
2. **Social Feed** — Follow sieves, discover public capsules, knowledge network (not a conversation platform)
3. **Obsidian Vault Import** — Web-based import of existing Obsidian vaults into Neural Sieve

## 1. Sieve Clipper (Forked Obsidian Web Clipper)

### What It Is

A Chrome/Firefox extension forked from [Obsidian Web Clipper](https://github.com/obsidianmd/obsidian-clipper) (MIT licensed), rebranded for Neural Sieve.

### What We Keep From Obsidian Clipper

- Page overlay UI for selecting content
- Template system for different content types
- Markdown conversion engine
- Highlight/selection capture
- Full-page capture
- Browser context menu integration ("Capture to Sieve")

### What We Change

- **Destination:** Instead of opening Obsidian app, POSTs to Neural Sieve `/api/capture/`
- **Auth:** User logs into their Sieve account via the extension popup (stores JWT)
- **Zero-field capture mode:** Default — one click, LLM extracts everything (title, tags, category, summary). No form to fill.
- **Optional preview mode:** Power users can toggle "preview before save" in extension options
- **Branding:** "Sieve Clipper" — new icon, colors, name
- **Toast notification:** After capture, small toast "Saved to your Sieve" with link to view

### Capture Flow

```
User clicks extension icon (or keyboard shortcut)
  -> Extension grabs page content (full page or selection)
  -> Converts to clean markdown (existing Clipper logic)
  -> POSTs to Neural Sieve API: { content, url, source_type }
  -> API runs LLM extraction pipeline
  -> Returns capsule with title, summary, tags, etc.
  -> Extension shows toast: "Captured: [title]"
```

## 2. Social Network & Discovery

### Core Concepts

- **Public Sieve** — Toggle in settings. Public sieves are discoverable. Their capsules appear in the global feed.
- **Follow** — You follow a sieve (not a person). New public capsules from followed sieves appear in your feed.
- **Feed** — Home feed shows your capsules + followed sieves' capsules, reverse-chronological.
- **Discover** — Browse public sieves by category, trending tags, or search.

### Data Model Additions

```sql
-- New table
CREATE TABLE follows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_sieve_id UUID NOT NULL REFERENCES sieves(id),
    followed_sieve_id UUID NOT NULL REFERENCES sieves(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(follower_sieve_id, followed_sieve_id)
);

-- New fields on sieves table
ALTER TABLE sieves ADD COLUMN avatar_url TEXT;
ALTER TABLE sieves ADD COLUMN bio TEXT;

-- Existing field already present
-- sieves.is_public BOOLEAN DEFAULT false
```

### Social Interactions (Intentionally Minimal)

- Follow / Unfollow a sieve
- Pin a capsule to your own sieve (repost/bookmark)
- View follower/following counts
- **No comments, no likes, no DMs** — knowledge network, not conversation platform

### Dashboard Pages

| Page | What It Shows |
|------|--------------|
| `/` (Feed) | Your capsules + followed sieves' capsules, reverse-chronological |
| `/sieve/@username` | Public sieve profile — capsules, bio, follower count |
| `/discover` | Browse public sieves, trending tags, search by topic |
| `/capture` | Quick capture form (web fallback for clipper) |
| `/import` | Obsidian vault import |
| `/settings` | Account, preferences, API key |

## 3. Feed Dashboard UX

### Home Feed (`/`)

- Infinite scroll, reverse-chronological
- Each capsule card shows:
  - **Title** (clickable -> expands to full view)
  - **Core insight** (one-liner hook)
  - **Tags** (clickable -> filter by tag)
  - **Source** (favicon + domain)
  - **Author sieve** (if from followed sieve, with avatar)
  - **Timestamp** ("2h ago", "3 days ago")
- Expandable: click to see full content, summary, all metadata inline
- Filter bar: All | My Capsules | Following | by category tabs

### Quick Capture in Feed

- Top of feed: capture bar (like "What's happening?")
- Paste URL -> auto-captures
- Type text -> captures as manual note

### Mobile-First

- Responsive, touch-friendly
- PWA support (existing manifest.json)
- Bottom nav on mobile: Feed | Discover | Capture | Profile
- Side nav on desktop

## 4. Obsidian Vault Import

### How It Works

1. **Import page** (`/import`) with two options:
   - **Select vault folder** — File System Access API (Chrome) or zip upload fallback
   - **Upload .zip** — works everywhere

2. **Processing pipeline:**
   - Scans for `.md` files
   - Parses YAML frontmatter (tags, aliases, dates)
   - Extracts markdown content body
   - Files with good frontmatter: maps directly to capsule fields
   - Files without metadata: runs through LLM extraction pipeline
   - Progress bar: "Processing 47/312 notes..."

3. **Preview + confirm:**
   - Summary: "Found 312 notes. 280 -> capsules, 32 skipped (empty/too short)"
   - Sample review before confirming
   - "Import All" creates capsules

4. **Deduplication:**
   - Same `source_url` or very similar `title` -> flagged as duplicate, skipped or overwrite option

### What We Don't Do Yet

- No two-way sync (postponed)
- No automatic re-import on vault changes
- No Obsidian plugin required

## 5. System Architecture

```
+-------------------+     +-------------------+
|  Sieve Clipper    |     |  Web Dashboard    |
|  (Chrome/FF ext)  |     |  (HTMX + Jinja2)  |
+--------+----------+     +--------+----------+
         |                         |
         |   POST /api/capture     |  HTMX routes
         |                         |
         v                         v
+---------------------------------------------+
|           Neural Sieve API                  |
|  (FastAPI, async)                           |
|                                             |
|  /api/capture    - LLM extraction           |
|  /api/capsules   - CRUD                     |
|  /api/sieves     - profiles, follow         |
|  /api/feed       - aggregated feed          |
|  /api/discover   - public sieve search      |
|  /api/import     - vault upload + process   |
|  /api/auth       - JWT + Google OAuth       |
+---------------------+-----------------------+
                      |
                      v
+---------------------------------------------+
|  PostgreSQL + (future: pgvector)            |
|  Users, Sieves, Capsules, Follows           |
+---------------------------------------------+
                      |
                      v
+---------------------------------------------+
|  MCP Server (for Claude Code users)         |
|  search, get_capsule, get_pinned, etc.      |
+---------------------------------------------+
```

## 6. Implementation Phases

| Phase | What | Why This Order |
|-------|------|----------------|
| **1. Social DB + API** | Follow table, feed endpoint, public sieve endpoints, sieve profile fields (bio, display_name, avatar_url) | Foundation for everything else |
| **2. Feed Dashboard** | Redesign as feed-first. Home feed, discover page, sieve profiles, follow/unfollow. Mobile-responsive. | Users see value immediately |
| **3. Sieve Clipper** | Fork Obsidian Web Clipper, rebrand, rewire to Neural Sieve API, one-click capture, auth via popup | Primary capture mechanism |
| **4. Vault Import** | `/import` page with zip upload, markdown parsing, LLM extraction, progress bar, dedup | Onboarding for Obsidian users |

## 7. What Stays The Same

- Existing capture pipeline (LLM extraction, SSRF protection)
- Existing auth (JWT + Google OAuth)
- MCP server (just needs new capsules flowing in)
- Skill compiler (unchanged)
- Deployment on Fly.io

## 8. Future (Not In This Design)

- Two-way Obsidian sync (postponed)
- Obsidian plugin (postponed)
- pgvector semantic search
- Mobile native app
- Revenue model / premium packs
- Team/workspace features
