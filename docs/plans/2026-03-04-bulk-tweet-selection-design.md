# Bulk Tweet Selection for Creator Capsules

**Date:** 2026-03-04
**Status:** Approved

## Problem

Creating creator capsules from tweets is slow — each tweet must be manually copied and captured one at a time. Admins need a way to select multiple tweets in bulk on a creator's Twitter profile and batch-create capsules.

## Design

### UX Flow

1. Admin visits a creator's Twitter profile (x.com/@username)
2. Extension popup shows **"Select Tweets"** button in the admin section (alongside "Add as Creator")
3. Clicking activates **selection mode** on the page:
   - Tweets get a hover highlight effect
   - Clicking a tweet toggles selection (selected = blue left border + slight background tint)
   - A **floating action bar** appears at the bottom: `"X selected" | [Capture All] | [Cancel]`
4. Clicking **"Capture All"** extracts text from all selected tweets and fires a batch capture request
5. Toast notifications show progress as each capsule completes
6. Selection mode deactivates when done

### Backend: Batch Capture Endpoint

**`POST /api/capture/batch`** (admin-only)

Request:
```json
{
  "items": [
    { "content": "tweet text", "source_url": "https://x.com/user/status/123" }
  ],
  "creator_id": "uuid",
  "source_type": "tweet"
}
```

Response:
```json
{
  "results": [
    { "status": "success", "capsule_id": "uuid", "title": "..." },
    { "status": "error", "error": "extraction failed" }
  ],
  "total": 5,
  "succeeded": 4,
  "failed": 1
}
```

- Reuses existing `CapturePipeline.process()` per item
- Parallel processing via `asyncio.gather()`
- Each item becomes one capsule in the creator's pack

### Extension Architecture

| File | Change |
|------|--------|
| `extension/src/core/admin-creators.ts` | Add "Select Tweets" button, send `enableTweetSelectionMode` message to content script |
| `extension/src/content.ts` | Handle `enableTweetSelectionMode` action — inject selection UI, manage selected tweets, handle capture |
| `extension/src/utils/twitter-extractor.ts` | New `extractTweetContent(element)` — extracts text + URL from tweet DOM element |
| `extension/src/utils/sieve-api-client.ts` | New `batchCapture()` method → `POST /api/capture/batch` |
| `src/sieve/api/capture/routes.py` | New `batch_capture` route handler |
| `src/sieve/api/capture/schemas.py` | New `BatchCaptureRequest` / `BatchCaptureResponse` Pydantic schemas |

### Tweet DOM Extraction

- Tweet text: `[data-testid="tweetText"]` → `.innerText`
- Tweet URL: timestamp link (`time` element's parent `<a>` href)
- Tweet container: `[data-testid="tweet"]` for click targets

### Constraints

- Admin-only feature (checked via `authUser.isAdmin`)
- Creator profile pages only (detected by existing `isTwitterProfile()`)
- Creator auto-matched by Twitter handle (existing logic)
- No max batch limit enforced (admin tool), soft cap ~50
- Parallel LLM extraction for speed
