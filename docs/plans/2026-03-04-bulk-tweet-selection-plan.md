# Bulk Tweet Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable admins to select multiple tweets on a creator's Twitter profile and batch-create capsules from them.

**Architecture:** New `POST /api/capture/batch` endpoint processes multiple items in parallel via `asyncio.gather()`. Extension content script injects a tweet selection mode on creator profile pages. Popup triggers selection mode; floating action bar on the page handles capture.

**Tech Stack:** Python/FastAPI (backend), TypeScript (extension content script + popup), Pydantic v2 (schemas), pytest-asyncio (tests)

---

### Task 1: Backend — Batch Capture Schemas

**Files:**
- Modify: `src/sieve/api/capsules/schemas.py`
- Test: `tests/test_batch_capture.py`

**Step 1: Write the failing test**

Create `tests/test_batch_capture.py`:

```python
from sieve.api.capsules.schemas import BatchCaptureItem, BatchCaptureRequest


def test_batch_capture_item_schema():
    item = BatchCaptureItem(content="tweet text", source_url="https://x.com/user/status/123")
    assert item.content == "tweet text"
    assert item.source_url == "https://x.com/user/status/123"


def test_batch_capture_item_source_url_optional():
    item = BatchCaptureItem(content="tweet text")
    assert item.source_url is None


def test_batch_capture_request_schema():
    req = BatchCaptureRequest(
        items=[
            BatchCaptureItem(content="tweet 1"),
            BatchCaptureItem(content="tweet 2"),
        ],
        creator_id="abc-123",
    )
    assert len(req.items) == 2
    assert req.creator_id == "abc-123"
    assert req.source_type == "tweet"


def test_batch_capture_request_source_type_default():
    req = BatchCaptureRequest(
        items=[BatchCaptureItem(content="tweet")],
        creator_id="abc",
    )
    assert req.source_type == "tweet"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_batch_capture.py -v`
Expected: FAIL with `ImportError: cannot import name 'BatchCaptureItem'`

**Step 3: Write minimal implementation**

Add to `src/sieve/api/capsules/schemas.py` (after the `SearchRequest` class at the end):

```python
class BatchCaptureItem(BaseModel):
    content: str
    source_url: str | None = None


class BatchCaptureRequest(BaseModel):
    items: list[BatchCaptureItem]
    creator_id: str
    source_type: str = "tweet"


class BatchCaptureResultItem(BaseModel):
    status: str  # "success" or "error"
    capsule_id: str | None = None
    title: str | None = None
    error: str | None = None


class BatchCaptureResponse(BaseModel):
    results: list[BatchCaptureResultItem]
    total: int
    succeeded: int
    failed: int
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_batch_capture.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/sieve/api/capsules/schemas.py tests/test_batch_capture.py
git commit -m "feat: add batch capture Pydantic schemas"
```

---

### Task 2: Backend — Batch Capture Route

**Files:**
- Modify: `src/sieve/api/capture/routes.py`
- Test: `tests/test_batch_capture.py`

**Step 1: Write the failing test**

Add to `tests/test_batch_capture.py`:

```python
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from sieve.api.auth.deps import create_access_token, hash_password
from sieve.db.models import Creator, Sieve, User


@pytest.fixture
async def admin_user(db_session):
    user = User(
        email="admin@example.com",
        password_hash=hash_password("adminpassword"),
        display_name="Admin User",
        username="admin",
        is_admin=True,
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Admin Sieve")
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def admin_cookies(admin_user):
    return {"sieve_token": create_access_token(str(admin_user.id))}


@pytest.fixture
async def creator(db_session):
    c = Creator(
        id=uuid.uuid4(),
        name="Test Creator",
        slug="test-creator",
        description="Test",
    )
    db_session.add(c)
    await db_session.commit()
    await db_session.refresh(c)
    return c


@pytest.mark.asyncio
async def test_batch_capture_success(app, admin_cookies, creator):
    mock_result = {
        "title": "Extracted Title",
        "executive_summary": "Summary",
        "core_insight": "Insight",
        "full_content": "Content",
        "tags": ["ai"],
        "keywords": ["ml"],
        "topics": ["tech"],
        "category": "AI",
        "domain": "Technology",
        "difficulty": "intermediate",
        "content_type": "insight",
        "author": "test",
        "source_url": None,
        "capture_method": "manual",
        "source_type": "tweet",
    }

    with patch(
        "sieve.api.capture.routes.CapturePipeline.process",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/capture/batch",
                json={
                    "items": [
                        {"content": "tweet one"},
                        {"content": "tweet two"},
                    ],
                    "creator_id": str(creator.id),
                },
                cookies=admin_cookies,
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert body["succeeded"] == 2
    assert body["failed"] == 0
    assert len(body["results"]) == 2
    assert all(r["status"] == "success" for r in body["results"])


@pytest.mark.asyncio
async def test_batch_capture_rejects_non_admin(app, db_session, creator):
    user = User(
        email="regular@example.com",
        password_hash=hash_password("password"),
        display_name="Regular User",
        username="regular",
        is_admin=False,
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Regular Sieve")
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)

    token = create_access_token(str(user.id))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/capture/batch",
            json={
                "items": [{"content": "tweet"}],
                "creator_id": str(creator.id),
            },
            cookies={"sieve_token": token},
        )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_batch_capture_creator_not_found(app, admin_cookies):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/capture/batch",
            json={
                "items": [{"content": "tweet"}],
                "creator_id": str(uuid.uuid4()),
            },
            cookies=admin_cookies,
        )
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_batch_capture.py::test_batch_capture_success -v`
Expected: FAIL with 404 (route doesn't exist)

**Step 3: Write minimal implementation**

Add to `src/sieve/api/capture/routes.py`, after the existing `capture` route:

```python
import asyncio

from sieve.api.auth.deps import require_admin
from sieve.api.capsules.schemas import (
    BatchCaptureRequest,
    BatchCaptureResponse,
    BatchCaptureResultItem,
    CaptureRequest,
)


@router.post("/batch", response_model=BatchCaptureResponse)
async def batch_capture(
    body: BatchCaptureRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Batch capture multiple content items as capsules for a creator pack.

    Admin-only. Processes all items in parallel via the LLM pipeline.
    """
    # Verify creator exists
    result = await db.execute(select(Creator).where(Creator.id == body.creator_id))
    creator = result.scalar_one_or_none()
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found"
        )

    async def process_one(item):
        pipeline = CapturePipeline()
        try:
            req = CaptureRequest(content=item.content, source_url=item.source_url)
            capsule_data = await pipeline.process(req)

            capsule = Capsule(
                sieve_id=None,
                pack_id=creator.id,
                title=capsule_data.get("title", "Untitled"),
                executive_summary=capsule_data.get("executive_summary", ""),
                core_insight=capsule_data.get("core_insight", ""),
                full_content=capsule_data.get("full_content", ""),
                tags=capsule_data.get("tags", []),
                keywords=capsule_data.get("keywords", []),
                topics=capsule_data.get("topics", []),
                category=capsule_data.get("category", ""),
                domain=capsule_data.get("domain", ""),
                difficulty=capsule_data.get("difficulty", "beginner"),
                content_type=capsule_data.get("content_type", "insight"),
                author=capsule_data.get("author", "personal"),
                source_url=item.source_url,
                capture_method="batch",
                source_type=body.source_type,
            )
            db.add(capsule)
            await db.flush()
            return BatchCaptureResultItem(
                status="success",
                capsule_id=str(capsule.id),
                title=capsule.title,
            )
        except Exception as e:
            return BatchCaptureResultItem(
                status="error",
                error=str(e),
            )

    results = await asyncio.gather(*[process_one(item) for item in body.items])
    await db.commit()

    # Update creator capsule count
    count_result = await db.execute(
        select(func.count()).where(Capsule.pack_id == creator.id)
    )
    creator.capsule_count = count_result.scalar() or 0
    await db.commit()

    succeeded = sum(1 for r in results if r.status == "success")
    return BatchCaptureResponse(
        results=list(results),
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
    )
```

Update the imports at the top of `src/sieve/api/capture/routes.py`:

```python
import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user, require_admin
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import (
    BatchCaptureRequest,
    BatchCaptureResponse,
    BatchCaptureResultItem,
    CapsuleResponse,
    CaptureRequest,
)
from sieve.api.capture.pipeline import CapturePipeline
from sieve.db.database import get_db
from sieve.db.models import Capsule, Creator, Sieve, User
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_batch_capture.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/sieve/api/capture/routes.py tests/test_batch_capture.py
git commit -m "feat: add POST /api/capture/batch endpoint for bulk capture"
```

---

### Task 3: Extension — API Client `batchCapture()` Method

**Files:**
- Modify: `extension/src/utils/sieve-api-client.ts`

**Step 1: Add batch capture types and function**

Add to `extension/src/utils/sieve-api-client.ts` (after the `CaptureResponse` interface):

```typescript
export interface BatchCaptureItem {
	content: string;
	source_url?: string;
}

export interface BatchCaptureRequest {
	items: BatchCaptureItem[];
	creator_id: string;
	source_type?: string;
}

export interface BatchCaptureResultItem {
	status: 'success' | 'error';
	capsule_id?: string;
	title?: string;
	error?: string;
}

export interface BatchCaptureResponse {
	results: BatchCaptureResultItem[];
	total: number;
	succeeded: number;
	failed: number;
}
```

Add the function (after `captureToSieve`):

```typescript
export async function batchCapture(
	serverUrl: string,
	apiKey: string,
	request: BatchCaptureRequest
): Promise<BatchCaptureResponse> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/capture/batch`, {
			method: 'POST',
			headers: apiHeaders(apiKey),
			body: JSON.stringify(request),
		});
	} catch {
		throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
	}

	if (!response.ok) {
		const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
		if (response.status === 401) {
			throw new SieveApiError('auth_expired', body.detail || 'Invalid API key', 401);
		}
		throw new SieveApiError(
			'server_error',
			body.detail || `Server error (${response.status})`,
			response.status
		);
	}

	return await response.json();
}
```

**Step 2: Commit**

```bash
git add extension/src/utils/sieve-api-client.ts
git commit -m "feat: add batchCapture() to extension API client"
```

---

### Task 4: Extension — Tweet Extraction Helper

**Files:**
- Modify: `extension/src/utils/twitter-extractor.ts`

**Step 1: Add tweet content extraction functions**

Add to the end of `extension/src/utils/twitter-extractor.ts`:

```typescript
export interface TweetContent {
    text: string;
    url: string | null;
}

/**
 * Extract text and URL from a tweet DOM element.
 * Expects the element to be or contain [data-testid="tweet"].
 */
export function extractTweetContent(tweetEl: Element): TweetContent | null {
    const textEl = tweetEl.querySelector('[data-testid="tweetText"]');
    const text = textEl?.textContent?.trim() || '';
    if (!text) return null;

    // Tweet URL is in the timestamp link: <a href="/user/status/123"><time ...></a>
    const timeLink = tweetEl.querySelector('time')?.closest('a') as HTMLAnchorElement | null;
    let url: string | null = null;
    if (timeLink?.href) {
        try {
            url = new URL(timeLink.href, window.location.origin).href;
        } catch {
            url = timeLink.href;
        }
    }

    return { text, url };
}
```

**Step 2: Commit**

```bash
git add extension/src/utils/twitter-extractor.ts
git commit -m "feat: add extractTweetContent helper for tweet DOM extraction"
```

---

### Task 5: Extension — Content Script Tweet Selection Mode

**Files:**
- Modify: `extension/src/content.ts`

**Step 1: Add selection mode handler**

Add the `enableTweetSelectionMode` action handler inside the `browser.runtime.onMessage.addListener` callback in `extension/src/content.ts` (after the `extractTwitterProfile` handler around line 422):

```typescript
	} else if (request.action === "enableTweetSelectionMode") {
		enableTweetSelectionMode(request.creatorId, request.serverUrl, request.apiKey);
		sendResponse({ success: true });
	}
```

Add the selection mode functions before the closing `})();` at the end of `extension/src/content.ts`:

```typescript
	let selectionModeActive = false;
	const selectedTweets = new Set<Element>();

	function enableTweetSelectionMode(creatorId: string, serverUrl: string, apiKey: string): void {
		if (selectionModeActive) return;
		selectionModeActive = true;
		selectedTweets.clear();

		// Inject selection styles
		const style = document.createElement('style');
		style.id = 'sieve-selection-style';
		style.textContent = `
			[data-testid="tweet"] {
				cursor: pointer !important;
				transition: border-left 0.15s, background 0.15s !important;
			}
			[data-testid="tweet"]:hover {
				border-left: 3px solid #7c6bf5 !important;
			}
			[data-testid="tweet"].sieve-selected {
				border-left: 3px solid #7c6bf5 !important;
				background: rgba(124, 107, 245, 0.08) !important;
			}
		`;
		document.head.appendChild(style);

		// Add click handlers to tweets
		document.addEventListener('click', tweetClickHandler, true);

		// Create floating action bar
		createSelectionBar(creatorId, serverUrl, apiKey);
	}

	function tweetClickHandler(e: MouseEvent): void {
		if (!selectionModeActive) return;

		// Don't intercept clicks on links, buttons, etc. inside tweets
		const target = e.target as Element;
		if (target.closest('a[href]') || target.closest('button') || target.closest('[role="button"]')) {
			// Allow link/button clicks unless it's a tweet's main clickable area
			return;
		}

		const tweetEl = target.closest('[data-testid="tweet"]');
		if (!tweetEl) return;

		e.preventDefault();
		e.stopPropagation();

		if (selectedTweets.has(tweetEl)) {
			selectedTweets.delete(tweetEl);
			tweetEl.classList.remove('sieve-selected');
		} else {
			selectedTweets.add(tweetEl);
			tweetEl.classList.add('sieve-selected');
		}

		updateSelectionCount();
	}

	function createSelectionBar(creatorId: string, serverUrl: string, apiKey: string): void {
		const bar = document.createElement('div');
		bar.id = 'sieve-selection-bar';
		bar.style.cssText = `
			position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
			z-index: 2147483647; background: #1a1a2e; color: #e0e0e0;
			border: 1px solid #333; border-radius: 12px; padding: 12px 20px;
			display: flex; align-items: center; gap: 16px;
			box-shadow: 0 8px 32px rgba(0,0,0,0.4);
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
			font-size: 14px;
		`;

		const countEl = document.createElement('span');
		countEl.id = 'sieve-selection-count';
		countEl.textContent = '0 selected';

		const captureBtn = document.createElement('button');
		captureBtn.textContent = 'Capture All';
		captureBtn.style.cssText = `
			background: #7c6bf5; color: white; border: none; border-radius: 6px;
			padding: 8px 16px; cursor: pointer; font-size: 14px; font-weight: 600;
		`;
		captureBtn.addEventListener('click', () => handleBatchCapture(creatorId, serverUrl, apiKey));

		const cancelBtn = document.createElement('button');
		cancelBtn.textContent = 'Cancel';
		cancelBtn.style.cssText = `
			background: transparent; color: #999; border: 1px solid #444;
			border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 14px;
		`;
		cancelBtn.addEventListener('click', disableSelectionMode);

		bar.appendChild(countEl);
		bar.appendChild(captureBtn);
		bar.appendChild(cancelBtn);
		document.body.appendChild(bar);
	}

	function updateSelectionCount(): void {
		const countEl = document.getElementById('sieve-selection-count');
		if (countEl) {
			countEl.textContent = `${selectedTweets.size} selected`;
		}
	}

	async function handleBatchCapture(creatorId: string, serverUrl: string, apiKey: string): Promise<void> {
		if (selectedTweets.size === 0) return;

		const { extractTweetContent } = await import('./utils/twitter-extractor');

		const items: { content: string; source_url?: string }[] = [];
		for (const tweetEl of selectedTweets) {
			const extracted = extractTweetContent(tweetEl);
			if (extracted) {
				items.push({
					content: extracted.text,
					source_url: extracted.url || undefined,
				});
			}
		}

		if (items.length === 0) {
			showSieveErrorToast('No tweet text could be extracted from selection');
			disableSelectionMode();
			return;
		}

		// Update UI to show progress
		const captureBtn = document.querySelector('#sieve-selection-bar button') as HTMLButtonElement;
		if (captureBtn) {
			captureBtn.disabled = true;
			captureBtn.textContent = `Capturing ${items.length}...`;
		}

		try {
			const { batchCapture } = await import('./utils/sieve-api-client');
			const result = await batchCapture(serverUrl, apiKey, {
				items,
				creator_id: creatorId,
			});

			const message = `${result.succeeded}/${result.total} capsules created` +
				(result.failed > 0 ? ` (${result.failed} failed)` : '');

			showSieveToast(message, '', serverUrl);
		} catch (err: any) {
			showSieveErrorToast(err.message || 'Batch capture failed');
		}

		disableSelectionMode();
	}

	function disableSelectionMode(): void {
		selectionModeActive = false;
		document.removeEventListener('click', tweetClickHandler, true);

		// Remove selection styling
		for (const el of selectedTweets) {
			el.classList.remove('sieve-selected');
		}
		selectedTweets.clear();

		// Remove injected elements
		document.getElementById('sieve-selection-style')?.remove();
		document.getElementById('sieve-selection-bar')?.remove();
	}
```

**Step 2: Build the extension to verify no TypeScript errors**

Run: `cd extension && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit**

```bash
git add extension/src/content.ts
git commit -m "feat: add tweet selection mode to content script"
```

---

### Task 6: Extension — Popup "Select Tweets" Button

**Files:**
- Modify: `extension/src/popup.html`
- Modify: `extension/src/core/admin-creators.ts`

**Step 1: Add button to popup HTML**

In `extension/src/popup.html`, after the `add-creator-btn` button line (around line 56), within the `add-creator-section` div, add:

```html
<button id="select-tweets-btn" style="width:100%;padding:0.5rem;background:#7c6bf5;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:0.85rem;margin-top:0.5rem">Select Tweets</button>
```

**Step 2: Wire up the button in admin-creators.ts**

In `extension/src/core/admin-creators.ts`, add a new function and call it from `initializeAdminSection`. After `setupAddCreatorButton(tabId);` (line 42), add:

```typescript
			setupSelectTweetsButton(tabId);
```

Add the new function (after `setupAddCreatorButton`):

```typescript
function setupSelectTweetsButton(tabId: number): void {
	const selectTweetsBtn = document.getElementById('select-tweets-btn');
	if (!selectTweetsBtn) return;

	selectTweetsBtn.addEventListener('click', async () => {
		if (!generalSettings.apiKey) return;

		const creatorId = getSelectedCreatorId();
		if (!creatorId) {
			const btn = selectTweetsBtn as HTMLButtonElement;
			btn.textContent = 'Select a creator first';
			setTimeout(() => { btn.textContent = 'Select Tweets'; }, 2000);
			return;
		}

		try {
			// Ensure content script is loaded
			await browser.runtime.sendMessage({ action: 'ensureContentScriptLoaded', tabId });

			// Send message to content script to enable selection mode
			await browser.runtime.sendMessage({
				action: 'sendMessageToTab',
				tabId,
				message: {
					action: 'enableTweetSelectionMode',
					creatorId,
					serverUrl: generalSettings.serverUrl,
					apiKey: generalSettings.apiKey,
				},
			});

			// Close the popup so the user can interact with the page
			window.close();
		} catch (err: any) {
			console.error('Failed to enable tweet selection mode:', err);
		}
	});
}
```

**Step 3: Build the extension to verify no errors**

Run: `cd extension && npm run build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add extension/src/popup.html extension/src/core/admin-creators.ts
git commit -m "feat: add Select Tweets button to extension popup admin section"
```

---

### Task 7: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS including the new `test_batch_capture.py` tests

**Step 2: Build extension**

Run: `cd extension && npm run build`
Expected: Build succeeds

**Step 3: Final commit if any fixes needed**

Only commit if something was fixed during this step.
