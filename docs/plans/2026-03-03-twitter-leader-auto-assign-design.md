# Twitter Leader Auto-Assign Design

## Goal

When the extension popup opens on a Twitter/X page, auto-detect the leader from the URL handle and pre-select them in the leader dropdown so captures are automatically assigned.

## Architecture

Extension-only change. No backend modifications needed — `listLeaders()` already returns `twitter_url`, and the capture endpoint already accepts `leader_id`.

## How It Works

1. User opens popup on any Twitter/X page (profile, tweet, or feed)
2. Extension extracts the handle from the URL's first path segment (e.g. `x.com/karpathy/status/123` -> `karpathy`)
3. After populating the leader dropdown via `listLeaders()`, match the handle against each leader's `twitter_url`
4. If match found, auto-select that leader in `#leader-select`
5. User clicks "Capture to Sieve" — capture includes the matched `leader_id`

## Scope

- **Admin-only**: Runs inside `initializeAdminSection()`, same gating as today
- **URL detection**: Extend `isTwitterProfile()` or add a new `extractTwitterHandle()` that works on any Twitter/X URL (profiles, tweets, feeds) — not just profile pages
- **Matching**: Compare extracted handle against the path segment of each leader's `twitter_url` (e.g. `https://x.com/karpathy` -> `karpathy`)
- **Fallback**: If no leader matches, dropdown stays on "No leader" — same as today

## Files to Modify

- `extension/src/utils/twitter-extractor.ts` — Add `extractTwitterHandle(url)` function
- `extension/src/core/admin-leaders.ts` — After `populateLeaderSelect()`, call auto-match logic to pre-select the leader

## Out of Scope

- Batch/multi-tweet capture (future V2)
- Auto-creating leaders from Twitter URLs (use existing "Add as Leader" flow)
- Non-Twitter URL matching
