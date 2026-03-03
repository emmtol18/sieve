# Extension API Key Auth & Theme Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace email/password login in the browser extension with API key paste, and retheme the extension to match the dashboard's warm cream/orange palette.

**Architecture:** Backend gets a new `/api/auth/verify-key` endpoint and `get_current_user` learns to accept `X-Api-Key` header as fallback to JWT. Extension stores the API key instead of JWT, uses it for all requests. Extension SCSS variables change from purple to dashboard colors.

**Tech Stack:** Python/FastAPI (backend), TypeScript (extension), SCSS (extension styles)

---

### Task 1: Backend — Add API Key Auth to `get_current_user`

**Files:**
- Modify: `src/sieve/api/auth/deps.py:78-101`
- Test: `tests/test_auth.py`

**Step 1: Write failing tests for X-Api-Key header support**

Add to `tests/test_auth.py`:

```python
def test_get_api_key_from_header():
    """X-Api-Key header is extracted when no JWT present."""
    request = AsyncMock(spec=Request)
    request.cookies = {}
    request.headers = {"x-api-key": "some-uuid-key"}
    token, is_api_key = get_token_from_request(request)
    assert token == "some-uuid-key"
    assert is_api_key is True


def test_jwt_takes_precedence_over_api_key():
    """JWT cookie wins over X-Api-Key header."""
    request = AsyncMock(spec=Request)
    request.cookies = {"sieve_token": "jwt-token"}
    request.headers = {"x-api-key": "api-key"}
    token, is_api_key = get_token_from_request(request)
    assert token == "jwt-token"
    assert is_api_key is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py::test_get_api_key_from_header tests/test_auth.py::test_jwt_takes_precedence_over_api_key -v`
Expected: FAIL — `get_token_from_request` returns `str | None`, not a tuple.

**Step 3: Update `get_token_from_request` and `get_current_user`**

In `src/sieve/api/auth/deps.py`, replace lines 78-101:

```python
def get_token_from_request(request: Request) -> tuple[str | None, bool]:
    """Extract auth credential from request.

    Returns (token, is_api_key). Checks in order:
    1. sieve_token cookie (JWT)
    2. Authorization: Bearer header (JWT)
    3. X-Api-Key header (API key)
    """
    token = request.cookies.get("sieve_token")
    if token:
        return token, False
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:], False
    api_key = request.headers.get("x-api-key")
    if api_key:
        return api_key, True
    return None, False


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token, is_api_key = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if is_api_key:
        result = await db.execute(select(User).where(User.api_key == token))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user
    user_id = verify_token(token)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

**Step 4: Fix the existing tests that call `get_token_from_request`**

The existing tests return a single value. Update them to destructure tuples:

In `tests/test_auth.py`, update:
- `test_get_token_from_cookie`: `assert get_token_from_request(request) == ("my-jwt-token", False)`
- `test_get_token_from_bearer_header`: `assert get_token_from_request(request) == ("my-jwt-token", False)`
- `test_get_token_cookie_takes_precedence`: `assert get_token_from_request(request) == ("cookie-token", False)`
- `test_get_token_missing_returns_none`: `assert get_token_from_request(request) == (None, False)`

**Step 5: Run all auth tests**

Run: `uv run pytest tests/test_auth.py -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/sieve/api/auth/deps.py tests/test_auth.py
git commit -m "feat: support X-Api-Key header in auth"
```

---

### Task 2: Backend — Add `/api/auth/verify-key` endpoint

**Files:**
- Modify: `src/sieve/api/auth/routes.py:96-103`
- Test: `tests/test_auth.py` (integration test)

**Step 1: Write failing integration test**

Add to `tests/test_auth.py`:

```python
@pytest.mark.asyncio
async def test_verify_key_returns_user(client, test_user):
    """GET /api/auth/verify-key with valid X-Api-Key returns user info."""
    user, _ = test_user
    response = await client.get(
        "/api/auth/verify-key",
        headers={"X-Api-Key": str(user.api_key)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["display_name"] == "Test User"
    assert data["api_key"] == str(user.api_key)


@pytest.mark.asyncio
async def test_verify_key_invalid_returns_401(client):
    """GET /api/auth/verify-key with invalid key returns 401."""
    response = await client.get(
        "/api/auth/verify-key",
        headers={"X-Api-Key": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401
```

These tests need the `client` and `test_user` fixtures from `conftest.py`. Add these imports at the top of `tests/test_auth.py`:

```python
import pytest
# existing imports stay
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py::test_verify_key_returns_user tests/test_auth.py::test_verify_key_invalid_returns_401 -v`
Expected: FAIL — 404 (endpoint doesn't exist)

**Step 3: Add the endpoint**

In `src/sieve/api/auth/routes.py`, add after the `/me` endpoint (after line 103):

```python
@router.get("/verify-key", response_model=UserResponse)
async def verify_key(user: User = Depends(get_current_user)):
    """Verify an API key and return user info.

    The extension sends X-Api-Key header, which get_current_user now handles.
    """
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        api_key=str(user.api_key),
    )
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_auth.py::test_verify_key_returns_user tests/test_auth.py::test_verify_key_invalid_returns_401 -v`
Expected: PASS

**Step 5: Run full test suite to check nothing broke**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add src/sieve/api/auth/routes.py tests/test_auth.py
git commit -m "feat: add /api/auth/verify-key endpoint for extension auth"
```

---

### Task 3: Extension — Retheme from Purple to Dashboard Colors

**Files:**
- Modify: `extension/src/styles/_variables.scss:1-11` (accent), `extension/src/styles/_variables.scss:196-209` (light base colors)

**Step 1: Update accent HSL values**

In `extension/src/styles/_variables.scss`, replace lines 9-11:

```scss
	--accent-h: 22;
	--accent-s: 78%;
	--accent-l: 41%;
```

This produces `hsl(22, 78%, 41%)` which is approximately `#ba5a12`, close to the dashboard's `#c06014`.

**Step 2: Update light mode base colors**

In `extension/src/styles/_variables.scss`, replace lines 196-209:

```scss
		--color-base-00: #faf8f5;
		--color-base-05: #f7f4f0;
		--color-base-10: #f5f2ee;
		--color-base-20: #f0ece7;
		--color-base-25: #e8e4df;

		--color-base-30: #e8e4df;
		--color-base-35: #d5d0ca;
		--color-base-40: #b5b0aa;

		--color-base-50: #b5b0aa;
		--color-base-60: #8a857e;
		--color-base-70: #8a857e;
		--color-base-100: #2d2a26;
```

**Step 3: Build and visually verify**

Run: `cd extension && npm run build` (or the project's build command)
Load the extension in Chrome and verify the popup shows warm cream background with orange-brown buttons instead of purple.

**Step 4: Commit**

```bash
git add extension/src/styles/_variables.scss
git commit -m "style: retheme extension from purple to dashboard warm cream/orange"
```

---

### Task 4: Extension — Update API Client for API Key Auth

**Files:**
- Modify: `extension/src/utils/sieve-api-client.ts` (full rewrite)

**Step 1: Replace API client**

Replace entire contents of `extension/src/utils/sieve-api-client.ts`:

```typescript
export interface CaptureRequest {
	content: string;
	url?: string;
	source_url?: string;
}

export interface CaptureResponse {
	id: string;
	title: string;
	executive_summary: string;
	created_at: string;
	[key: string]: unknown;
}

export class SieveApiError extends Error {
	code: 'auth_expired' | 'network_error' | 'server_error';
	status?: number;

	constructor(
		code: 'auth_expired' | 'network_error' | 'server_error',
		message: string,
		status?: number
	) {
		super(code);
		this.code = code;
		this.message = message;
		this.status = status;
	}
}

function apiHeaders(apiKey: string): Record<string, string> {
	return {
		'Content-Type': 'application/json',
		'X-Api-Key': apiKey,
	};
}

export async function verifyApiKey(
	serverUrl: string,
	apiKey: string
): Promise<{ id: string; email: string; display_name: string; api_key: string }> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/auth/verify-key`, {
			method: 'GET',
			headers: { 'X-Api-Key': apiKey },
		});
	} catch {
		throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
	}

	if (!response.ok) {
		if (response.status === 401) {
			throw new SieveApiError('auth_expired', 'Invalid API key', 401);
		}
		throw new SieveApiError('server_error', 'Failed to verify API key');
	}

	return await response.json();
}

export async function captureToSieve(
	serverUrl: string,
	apiKey: string,
	request: CaptureRequest
): Promise<CaptureResponse> {
	let response: Response;

	try {
		response = await fetch(`${serverUrl}/api/capture/`, {
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
git commit -m "refactor: replace JWT auth with API key in extension API client"
```

---

### Task 5: Extension — Update Storage and Types for API Key

**Files:**
- Modify: `extension/src/types/types.ts:55`
- Modify: `extension/src/utils/storage-utils.ts:9,54,90,127,165`

**Step 1: Update Settings interface**

In `extension/src/types/types.ts`, replace line 55:

```typescript
	apiKey: string | null;
```

(was `authToken: string | null;`)

**Step 2: Update storage-utils.ts**

In `extension/src/utils/storage-utils.ts`, apply these changes:

Line 9: `authToken: null,` → `apiKey: null,`

Line 54: `authToken?: string | null;` → `apiKey?: string | null;`

Line 90: `authToken: null,` → `apiKey: null,`

Line 127: `authToken: data.sieve_auth?.authToken ?? defaultSettings.authToken,` → `apiKey: data.sieve_auth?.apiKey ?? data.sieve_auth?.authToken ?? defaultSettings.apiKey,`

Note: The fallback to `authToken` on line 127 handles migration — existing users with the old key name still get loaded. On the next `saveSettings()`, it writes as `apiKey`.

Line 165: `authToken: generalSettings.authToken,` → `apiKey: generalSettings.apiKey,`

**Step 3: Commit**

```bash
git add extension/src/types/types.ts extension/src/utils/storage-utils.ts
git commit -m "refactor: rename authToken to apiKey in extension storage"
```

---

### Task 6: Extension — Update Popup HTML and Auth Flow

**Files:**
- Modify: `extension/src/popup.html:50-68`
- Modify: `extension/src/core/popup.ts:10,881-956,1125-1127,1157,1174,1207`

**Step 1: Replace popup auth form**

In `extension/src/popup.html`, replace lines 50-68:

```html
			<div id="auth-section">
				<div id="auth-login" style="display: none;">
					<div class="auth-form">
						<input id="login-api-key" type="text" placeholder="Paste your API key" class="auth-input" />
						<div class="auth-actions">
							<button id="login-btn" class="mod-cta">Connect</button>
							<a id="get-key-link" class="auth-link">Get your key from Settings &#8594;</a>
						</div>
						<p id="login-error" class="error-message" style="display: none;"></p>
					</div>
				</div>
				<div id="auth-user" style="display: none;">
					<div class="auth-user-info">
						<span id="auth-username"></span>
						<a id="logout-link" class="auth-link">Disconnect</a>
					</div>
				</div>
			</div>
```

**Step 2: Update popup.ts imports**

In `extension/src/core/popup.ts`, line 10, replace:

```typescript
import { verifyApiKey, captureToSieve, SieveApiError } from '../utils/sieve-api-client';
```

(removes `loginToSieve` and `fetchCurrentUser` imports)

**Step 3: Update `initializeAuth` function**

In `extension/src/core/popup.ts`, replace `initializeAuth` (lines 881-894):

```typescript
async function initializeAuth(): Promise<void> {
	const loginSection = document.getElementById('auth-login')!;
	const userSection = document.getElementById('auth-user')!;

	if (generalSettings.apiKey && generalSettings.authUser) {
		loginSection.style.display = 'none';
		userSection.style.display = 'flex';
		const usernameEl = document.getElementById('auth-username')!;
		usernameEl.textContent = generalSettings.authUser.displayName || generalSettings.authUser.email;
	} else {
		loginSection.style.display = 'block';
		userSection.style.display = 'none';
	}
}
```

**Step 4: Update `setupAuthListeners`**

In `extension/src/core/popup.ts`, replace `setupAuthListeners` (lines 896-905):

```typescript
function setupAuthListeners(): void {
	document.getElementById('login-btn')?.addEventListener('click', handleLogin);
	document.getElementById('login-api-key')?.addEventListener('keydown', (e) => {
		if (e.key === 'Enter') handleLogin();
	});
	document.getElementById('logout-link')?.addEventListener('click', handleLogout);
	document.getElementById('get-key-link')?.addEventListener('click', () => {
		browser.tabs.create({ url: `${generalSettings.serverUrl}/settings` });
	});
}
```

**Step 5: Rewrite `handleLogin`**

In `extension/src/core/popup.ts`, replace `handleLogin` (lines 907-948):

```typescript
async function handleLogin(): Promise<void> {
	const keyInput = document.getElementById('login-api-key') as HTMLInputElement;
	const errorEl = document.getElementById('login-error')!;
	const loginBtn = document.getElementById('login-btn') as HTMLButtonElement;
	const apiKey = keyInput.value.trim();

	if (!apiKey) {
		errorEl.textContent = 'Please paste your API key';
		errorEl.style.display = 'block';
		return;
	}

	loginBtn.disabled = true;
	loginBtn.textContent = 'Connecting...';
	errorEl.style.display = 'none';

	try {
		const user = await verifyApiKey(generalSettings.serverUrl, apiKey);
		generalSettings.apiKey = apiKey;
		generalSettings.authUser = {
			email: user.email,
			username: '',
			displayName: user.display_name,
		};
		await saveSettings();
		await initializeAuth();
		determineMainAction();
	} catch (err) {
		if (err instanceof SieveApiError) {
			errorEl.textContent = err.message;
		} else {
			errorEl.textContent = 'Connection failed. Check your server URL.';
		}
		errorEl.style.display = 'block';
	} finally {
		loginBtn.disabled = false;
		loginBtn.textContent = 'Connect';
	}
}
```

**Step 6: Update `handleLogout`**

In `extension/src/core/popup.ts`, replace `handleLogout` (lines 950-956):

```typescript
async function handleLogout(): Promise<void> {
	generalSettings.apiKey = null;
	generalSettings.authUser = null;
	await saveSettings();
	await initializeAuth();
	determineMainAction();
}
```

**Step 7: Update `determineMainAction` and `handleCaptureToSieve`**

In `extension/src/core/popup.ts`:

- Line 1125: `if (!generalSettings.authToken)` → `if (!generalSettings.apiKey)`
- Line 1126: `'Sign in to capture'` → `'Connect to capture'`
- Line 1157: `if (!generalSettings.authToken)` → `if (!generalSettings.apiKey)`
- Line 1158: `'Please sign in first'` → `'Please connect first'`
- Line 1174: `generalSettings.authToken,` → `generalSettings.apiKey,`
- Line 1207: `generalSettings.authToken = null;` → `generalSettings.apiKey = null;`
- Line 1211: `'Session expired. Please sign in again.'` → `'API key invalid. Please reconnect.'`

**Step 8: Commit**

```bash
git add extension/src/popup.html extension/src/core/popup.ts
git commit -m "feat: replace email/password login with API key paste in extension popup"
```

---

### Task 7: Extension — Update Background Script

**Files:**
- Modify: `extension/src/background.ts:35,38,411,427,482,485,595,598`

**Step 1: Replace all `authToken` references with `apiKey`**

In `extension/src/background.ts`:

- Line 35: `if (settings.authToken)` → `if (settings.apiKey)`
- Line 38: `authToken: settings.authToken,` → `apiKey: settings.apiKey,`
- Line 411: `const { authToken, serverUrl } = typedRequest as any;` → `const { apiKey, serverUrl } = typedRequest as any;`
- Line 427: `'Authorization': \`Bearer ${authToken}\`,` → `'X-Api-Key': apiKey,`
- Line 436: `'Session expired. Please sign in.'` → `'API key invalid. Please reconnect.'`
- Line 482: `if (settings.authToken)` → `if (settings.apiKey)`
- Line 485: `authToken: settings.authToken,` → `apiKey: settings.apiKey,`
- Line 595: `if (settings.authToken)` → `if (settings.apiKey)`
- Line 598: `authToken: settings.authToken,` → `apiKey: settings.apiKey,`

**Step 2: Commit**

```bash
git add extension/src/background.ts
git commit -m "refactor: use apiKey instead of authToken in background script"
```

---

### Task 8: Extension — Update Settings Page

**Files:**
- Modify: `extension/src/settings.html:39-63`
- Modify: `extension/src/managers/general-settings.ts:185-219`

**Step 1: Replace account section HTML**

In `extension/src/settings.html`, replace lines 39-63:

```html
					<div class="settings-section" id="account-section" style="display: none;">
						<h2>Account</h2>
						<div class="setting-item">
							<label>Server URL</label>
							<input id="server-url-input" type="url" class="setting-input" placeholder="https://app.neuralsieve.com" />
						</div>
						<div id="account-logged-in" style="display: none;">
							<div class="setting-item">
								<label>Connected as</label>
								<span id="settings-user-email"></span>
							</div>
							<button id="settings-logout-btn" class="mod-warning">Disconnect</button>
						</div>
						<div id="account-logged-out" style="display: none;">
							<div class="setting-item">
								<label>API Key</label>
								<input id="settings-api-key-input" type="text" class="setting-input" placeholder="Paste your API key" />
							</div>
							<div class="setting-item">
								<a id="settings-get-key-link" href="#" style="font-size: var(--font-ui-smaller); color: var(--text-muted);">Get your key from Dashboard Settings &#8594;</a>
							</div>
							<button id="settings-connect-btn" class="mod-cta">Connect</button>
							<p id="settings-connect-error" class="error-message" style="display: none;"></p>
						</div>
						<h3>Capture Mode</h3>
						<div class="setting-item">
							<label>Default capture mode</label>
							<select id="capture-mode-select" class="dropdown">
								<option value="quick">Quick — one click, no popup</option>
								<option value="full">Full — open popup with preview</option>
							</select>
						</div>
					</div>
```

**Step 2: Update general-settings.ts**

In `extension/src/managers/general-settings.ts`, replace `initializeAccountSettings` (lines 185-220):

```typescript
function initializeAccountSettings(): void {
	const serverUrlInput = document.getElementById('server-url-input') as HTMLInputElement;
	const captureModeSelect = document.getElementById('capture-mode-select') as HTMLSelectElement;
	const loggedIn = document.getElementById('account-logged-in')!;
	const loggedOut = document.getElementById('account-logged-out')!;

	if (serverUrlInput) serverUrlInput.value = generalSettings.serverUrl;
	if (captureModeSelect) captureModeSelect.value = generalSettings.captureMode;

	if (generalSettings.authUser) {
		if (loggedIn) loggedIn.style.display = 'block';
		if (loggedOut) loggedOut.style.display = 'none';
		const emailSpan = document.getElementById('settings-user-email');
		if (emailSpan) emailSpan.textContent = generalSettings.authUser.email;
	} else {
		if (loggedIn) loggedIn.style.display = 'none';
		if (loggedOut) loggedOut.style.display = 'block';
	}

	serverUrlInput?.addEventListener('change', async () => {
		generalSettings.serverUrl = serverUrlInput.value.replace(/\/+$/, '');
		await saveSettings();
	});

	captureModeSelect?.addEventListener('change', async () => {
		generalSettings.captureMode = captureModeSelect.value as 'quick' | 'full';
		await saveSettings();
	});

	document.getElementById('settings-logout-btn')?.addEventListener('click', async () => {
		generalSettings.apiKey = null;
		generalSettings.authUser = null;
		await saveSettings();
		initializeAccountSettings();
	});

	document.getElementById('settings-get-key-link')?.addEventListener('click', (e) => {
		e.preventDefault();
		browser.tabs.create({ url: `${generalSettings.serverUrl}/settings` });
	});

	document.getElementById('settings-connect-btn')?.addEventListener('click', async () => {
		const keyInput = document.getElementById('settings-api-key-input') as HTMLInputElement;
		const errorEl = document.getElementById('settings-connect-error')!;
		const connectBtn = document.getElementById('settings-connect-btn') as HTMLButtonElement;
		const apiKey = keyInput.value.trim();

		if (!apiKey) {
			errorEl.textContent = 'Please paste your API key';
			errorEl.style.display = 'block';
			return;
		}

		connectBtn.disabled = true;
		connectBtn.textContent = 'Connecting...';
		errorEl.style.display = 'none';

		try {
			const { verifyApiKey, SieveApiError } = await import('../utils/sieve-api-client');
			const user = await verifyApiKey(generalSettings.serverUrl, apiKey);
			generalSettings.apiKey = apiKey;
			generalSettings.authUser = {
				email: user.email,
				username: '',
				displayName: user.display_name,
			};
			await saveSettings();
			initializeAccountSettings();
		} catch (err: any) {
			errorEl.textContent = err.message || 'Connection failed';
			errorEl.style.display = 'block';
		} finally {
			connectBtn.disabled = false;
			connectBtn.textContent = 'Connect';
		}
	});
}
```

Note: We dynamically import `sieve-api-client` since `general-settings.ts` may not already import it. Alternatively, add a static import at the top of the file.

**Step 3: Commit**

```bash
git add extension/src/settings.html extension/src/managers/general-settings.ts
git commit -m "feat: add API key connect flow to extension settings page"
```

---

### Task 9: Build, Verify, Final Commit

**Step 1: Build extension**

Run: `cd extension && npm run build`
Expected: Build succeeds with no TypeScript errors

**Step 2: Start backend**

Run: `uv run sieve serve`

**Step 3: Manual verification checklist**

- [ ] Load extension in Chrome
- [ ] Popup shows warm cream/orange theme (not purple)
- [ ] Popup shows API key input (not email/password)
- [ ] "Get your key from Settings" link opens dashboard settings page
- [ ] Copy API key from dashboard settings, paste into extension popup
- [ ] Click "Connect" — shows username, button changes to "Capture to Sieve"
- [ ] Capture a page — works correctly
- [ ] Click "Disconnect" — returns to API key input
- [ ] Extension settings page also shows connect/disconnect flow

**Step 4: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 5: Final commit (if any leftover changes)**

```bash
git add -A
git commit -m "chore: extension API key auth and theme cleanup"
```
