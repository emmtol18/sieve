# Creator Packs — Personal vs Public Capsule Separation

**Goal:** Capsules captured to a creator belong to the creator's public pack, not the admin's personal sieve. Rename "leader" → "creator" everywhere. Users can browse creator packs and save capsules into their own sieve.

**Architecture:** Either/or model — a capsule belongs to a personal sieve OR a creator pack, never both. Users can copy creator capsules into their personal sieve.

---

## 1. Rename: leader → creator

Global rename across the entire codebase:

- **Database:** `leaders` table → `creators` table. FK column `pack_id` stays (it already references the entity generically).
- **API routes:** `/api/leaders/` → `/api/creators/`
- **Schemas:** `LeaderCreate`, `LeaderResponse`, etc. → `CreatorCreate`, `CreatorResponse`
- **Models:** `Leader` → `Creator`
- **Extension:** `admin-leaders.ts` → `admin-creators.ts`, "Add as Leader" → "Add as Creator", leader-select → creator-select
- **Dashboard:** Any leader references in templates, HTMX routes
- **Docs:** DEPLOYMENT.md, plan docs

## 2. Data model change

- `Capsule.sieve_id` becomes **nullable** (currently NOT NULL).
- Capture to creator: `pack_id = creator.id`, `sieve_id = NULL`
- Capture to personal: `sieve_id = user_sieve.id`, `pack_id = NULL`
- Migration: alter `sieve_id` to nullable, no data changes needed (existing capsules keep their sieve_id).

## 3. Capture flow

**Server (`POST /api/capture/`):**
- If `creator_id` is provided → set `pack_id`, leave `sieve_id` NULL
- If no `creator_id` → set `sieve_id` to user's sieve (current behavior)

**Extension popup (admin):**
- Creator dropdown stays as-is (renamed from "leader")
- "No creator" selected → personal sieve
- Creator selected → creator's pack

**Quick capture (background.ts):**
- Same logic: auto-match Twitter handle → creator → capture to creator pack

## 4. "Save to My Sieve" — user copies a creator capsule

**New endpoint: `POST /api/capsules/{id}/save`**
- Authenticated user calls this on a creator pack capsule
- Server creates a copy in the user's personal sieve
- Sets `source_type = "creator_pack"` on the copy
- Original capsule is untouched

**Dashboard UI:**
- Creator pack capsule pages show a "Save to My Sieve" button
- Discover page capsule cards get a save icon

## 5. Scope of rename

| Location | Old | New |
|----------|-----|-----|
| DB table | `leaders` | `creators` |
| Model class | `Leader` | `Creator` |
| API prefix | `/api/leaders/` | `/api/creators/` |
| Schemas | `LeaderCreate`, `LeaderResponse`, etc. | `CreatorCreate`, `CreatorResponse`, etc. |
| Extension module | `admin-leaders.ts` | `admin-creators.ts` |
| Extension UI text | "Add as Leader", "No leader" | "Add as Creator", "No creator" |
| API client | `createLeader`, `listLeaders` | `createCreator`, `listCreators` |
| Dashboard routes | `/leaders/`, leader references | `/creators/`, creator references |
| CaptureRequest field | `leader_id` | `creator_id` |
| Alembic migration | rename table `leaders` → `creators` | |
