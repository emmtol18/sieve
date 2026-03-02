# Sieve Clipper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fork the Obsidian Web Clipper (MIT) and transform it into the Sieve Clipper — a browser extension that POSTs captured content to Neural Sieve's `/api/capture/` endpoint with one-click zero-field capture.

**Architecture:** Surgical fork — copy the full Obsidian Clipper source into `extension/`, then make targeted changes: replace `obsidian-note-creator.ts` with an API client, add auth UI to the popup, rebrand all user-facing strings, remove the LLM Interpreter feature. Keep the template engine, highlighter, reader mode, and multi-browser support intact.

**Tech Stack:** TypeScript, Webpack 5, Vitest, webextension-polyfill, Manifest V3 (Chrome/Firefox/Safari). Build: `npm run build`. Test: `npm test`.

**Design doc:** `docs/plans/2026-03-02-sieve-clipper-design.md`

---

## Task 1: Clone and set up the fork

**Files:**
- Create: `extension/` directory (copy from Obsidian Clipper)

**Step 1: Clone the Obsidian Web Clipper**

```bash
git clone --depth 1 git@github.com:obsidianmd/obsidian-clipper.git /tmp/obsidian-clipper
```

**Step 2: Copy source into extension/**

```bash
mkdir -p extension
# Copy source files (not .git, not node_modules)
cp -r /tmp/obsidian-clipper/src extension/src
cp /tmp/obsidian-clipper/package.json extension/package.json
cp /tmp/obsidian-clipper/tsconfig.json extension/tsconfig.json
cp /tmp/obsidian-clipper/webpack.config.js extension/webpack.config.js
cp /tmp/obsidian-clipper/vitest.config.ts extension/vitest.config.ts
cp /tmp/obsidian-clipper/LICENSE extension/LICENSE-obsidian-clipper
cp -r /tmp/obsidian-clipper/tests extension/tests
```

Note: Also check for any additional config files at the root (`.browserslistrc`, etc.) and copy those too.

**Step 3: Update package.json**

Change these fields:

```json
{
  "name": "sieve-clipper",
  "version": "0.1.0",
  "description": "Capture knowledge to your Neural Sieve. One click, zero fields."
}
```

Keep all dependencies and scripts unchanged.

**Step 4: Verify the fork builds**

```bash
cd extension && npm install && npm run build:chrome
```

Expected: Successful build, outputs to `extension/dist/`.

**Step 5: Verify tests pass**

```bash
cd extension && npm test
```

Expected: All existing tests pass.

**Step 6: Commit**

```bash
git add extension/
git commit -m "chore: fork Obsidian Web Clipper (MIT) as extension base"
```

---

## Task 2: Rebrand manifests

**Files:**
- Modify: `extension/src/manifest.chrome.json`
- Modify: `extension/src/manifest.firefox.json`
- Modify: `extension/src/manifest.safari.json`

**Step 1: Update Chrome manifest**

In `extension/src/manifest.chrome.json`:

These reference i18n strings via `__MSG_extensionName__`, so the actual name/description change happens in locale files. But we need to update:

- Change `"commands"` key descriptions to reference "Sieve" instead of "Obsidian"
- Change side panel `"default_title"` to `"Sieve Clipper"`
- Change keyboard shortcut descriptions: `"Clip this page"` → `"Capture this page"`, `"Quick clip"` → `"Quick capture"`

**Step 2: Update Firefox manifest**

Same changes as Chrome, plus:
- Change `browser_specific_settings.gecko.id` to `"clipper@neuralsieve.com"` (new extension ID)

**Step 3: Update Safari manifest**

Same name/description changes.

**Step 4: Verify build still works**

```bash
cd extension && npm run build:chrome
```

**Step 5: Commit**

```bash
git add extension/src/manifest.*.json
git commit -m "chore: rebrand extension manifests for Sieve Clipper"
```

---

## Task 3: Rebrand English locale and HTML files

**Files:**
- Modify: `extension/src/_locales/en/messages.json`
- Modify: `extension/src/popup.html`
- Modify: `extension/src/settings.html`
- Modify: `extension/src/side-panel.html`

**Step 1: Update English locale**

In `extension/src/_locales/en/messages.json`, update these keys:

- `"extensionName"` → `{ "message": "Sieve Clipper" }`
- `"extensionDescription"` → `{ "message": "Capture knowledge to your Neural Sieve. One click, zero fields." }`
- Any keys containing "Obsidian" → replace with "Sieve"/"Neural Sieve"
- Any keys referencing "vault" → replace with "Sieve" or remove
- Any keys referencing "clip" in user-facing text → replace with "capture"

Search for all occurrences of "Obsidian", "vault", "Clip" (capitalized, user-facing) in the messages file and replace appropriately.

**Step 2: Update popup.html**

In `extension/src/popup.html`:
- Change `<title>` fallback text from "Obsidian Web Clipper" to "Sieve Clipper"
- Change `#clip-btn` default text from "Add to Obsidian" to "Capture to Sieve"

**Step 3: Update settings.html**

In `extension/src/settings.html`:
- Change any hardcoded "Obsidian" references to "Sieve"
- Update page title

**Step 4: Update side-panel.html**

Same pattern — change "Obsidian" to "Sieve".

**Step 5: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 6: Commit**

```bash
git add extension/src/_locales/en/ extension/src/popup.html extension/src/settings.html extension/src/side-panel.html
git commit -m "chore: rebrand English locale and HTML files for Sieve Clipper"
```

---

## Task 4: Rebrand all non-English locales

**Files:**
- Modify: `extension/src/_locales/*/messages.json` (34 locale directories)

**Step 1: Script the replacement**

Write a quick script to do search-and-replace across all locale files:

```bash
cd extension/src/_locales
for dir in */; do
  if [ "$dir" != "en/" ]; then
    # Replace "Obsidian Web Clipper" with "Sieve Clipper" in message values
    sed -i '' 's/Obsidian Web Clipper/Sieve Clipper/g' "$dir/messages.json"
    # Replace standalone "Obsidian" in message values (careful not to replace in keys)
    sed -i '' 's/"message": "\(.*\)Obsidian\(.*\)"/"message": "\1Neural Sieve\2"/g' "$dir/messages.json"
  fi
done
```

Note: This is a rough pass. After running, manually review a few locale files to ensure correctness. Some strings may need more nuanced replacement (e.g., "Add to Obsidian" → "Capture to Sieve" is different from "Obsidian settings" → "Sieve settings").

**Step 2: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 3: Commit**

```bash
git add extension/src/_locales/
git commit -m "chore: rebrand all locale files for Sieve Clipper"
```

---

## Task 5: Add auth types and storage

**Files:**
- Modify: `extension/src/types/types.ts`
- Modify: `extension/src/utils/storage-utils.ts`

**Step 1: Update types**

In `extension/src/types/types.ts`, add to the `Settings` interface:

```typescript
// Add to Settings interface
serverUrl: string;
authToken: string | null;
authUser: {
  email: string;
  username: string;
  displayName: string;
} | null;
captureMode: 'quick' | 'full';
```

Remove from `Settings` interface:
- `vaults: string[]`
- `legacyMode: boolean`
- `silentOpen: boolean`
- `interpreterModel?: string`
- `models: ModelConfig[]`
- `providers: Provider[]`
- `interpreterEnabled: boolean`
- `interpreterAutoRun: boolean`
- `defaultPromptContext: string`

Remove these interfaces entirely:
- `ModelConfig`
- `Provider`

Change `SaveBehavior` type:
```typescript
export type SaveBehavior = 'captureToSieve' | 'saveFile' | 'copyToClipboard';
```

Remove from `Template` interface:
- `behavior` field (or make optional for backwards compat during migration)
- `vault?: string` field
- `path` field — remove or repurpose

Keep `noteNameFormat` but note it won't be used for API capture (server generates title).

**Step 2: Update storage-utils defaults**

In `extension/src/utils/storage-utils.ts`, update the `generalSettings` defaults:

```typescript
// Replace these defaults in the generalSettings object:
serverUrl: 'https://app.neuralsieve.com',
authToken: null,
authUser: null,
captureMode: 'quick' as const,
saveBehavior: 'captureToSieve' as SaveBehavior,

// Remove these defaults:
// vaults: []
// legacyMode: false
// silentOpen: false
// interpreterModel: undefined
// models: []
// providers: []
// interpreterEnabled: false
// interpreterAutoRun: false
// defaultPromptContext: ''
```

Update `loadSettings()` to load the new fields from storage and merge defaults.

Update `saveSettings()` to persist the new fields.

**Step 3: Verify build and tests**

```bash
cd extension && npm run build:chrome && npm test
```

Some existing tests may break if they reference removed types — fix those.

**Step 4: Commit**

```bash
git add extension/src/types/types.ts extension/src/utils/storage-utils.ts
git commit -m "feat: add Neural Sieve auth types and storage, remove Obsidian-specific fields"
```

---

## Task 6: Create sieve-api-client (with tests)

**Files:**
- Create: `extension/src/utils/sieve-api-client.ts`
- Create: `extension/tests/sieve-api-client.test.ts`
- Delete: `extension/src/utils/obsidian-note-creator.ts` (after confirming no other imports)

**Step 1: Write the failing test**

Create `extension/tests/sieve-api-client.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { captureToSieve, CaptureRequest, CaptureResponse } from '../src/utils/sieve-api-client';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('captureToSieve', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should POST to /api/capture/ with content and auth header', async () => {
    const mockResponse: CaptureResponse = {
      id: 'abc-123',
      title: 'Test Capsule',
      executive_summary: 'A test',
      created_at: '2026-03-02T00:00:00Z',
    };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => mockResponse,
    });

    const request: CaptureRequest = {
      content: '# Hello World\n\nSome content here.',
      url: 'https://example.com/article',
    };

    const result = await captureToSieve(
      'https://app.neuralsieve.com',
      'test-jwt-token',
      request
    );

    expect(mockFetch).toHaveBeenCalledWith(
      'https://app.neuralsieve.com/api/capture/',
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer test-jwt-token',
        },
        body: JSON.stringify(request),
      })
    );
    expect(result.title).toBe('Test Capsule');
    expect(result.id).toBe('abc-123');
  });

  it('should throw on 401 with auth_expired error', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid token' }),
    });

    await expect(
      captureToSieve('https://app.neuralsieve.com', 'expired-token', {
        content: 'test',
      })
    ).rejects.toThrow('auth_expired');
  });

  it('should throw on network error', async () => {
    mockFetch.mockRejectedValueOnce(new Error('Failed to fetch'));

    await expect(
      captureToSieve('https://app.neuralsieve.com', 'token', {
        content: 'test',
      })
    ).rejects.toThrow('network_error');
  });

  it('should throw on server error with message', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal server error' }),
    });

    await expect(
      captureToSieve('https://app.neuralsieve.com', 'token', {
        content: 'test',
      })
    ).rejects.toThrow('server_error');
  });
});
```

**Step 2: Run the test to verify it fails**

```bash
cd extension && npx vitest run tests/sieve-api-client.test.ts
```

Expected: FAIL — module not found.

**Step 3: Implement the API client**

Create `extension/src/utils/sieve-api-client.ts`:

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
  constructor(
    public code: 'auth_expired' | 'network_error' | 'server_error',
    message: string,
    public status?: number
  ) {
    super(code);
    this.message = message;
  }
}

export async function captureToSieve(
  serverUrl: string,
  authToken: string,
  request: CaptureRequest
): Promise<CaptureResponse> {
  let response: Response;

  try {
    response = await fetch(`${serverUrl}/api/capture/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify(request),
    });
  } catch (err) {
    throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
    if (response.status === 401) {
      throw new SieveApiError('auth_expired', body.detail || 'Session expired', 401);
    }
    throw new SieveApiError(
      'server_error',
      body.detail || `Server error (${response.status})`,
      response.status
    );
  }

  return await response.json();
}

export async function loginToSieve(
  serverUrl: string,
  email: string,
  password: string
): Promise<{ access_token: string; api_key: string }> {
  let response: Response;

  try {
    response = await fetch(`${serverUrl}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
  } catch (err) {
    throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
    if (response.status === 401) {
      throw new SieveApiError('auth_expired', 'Invalid email or password', 401);
    }
    throw new SieveApiError(
      'server_error',
      body.detail || `Server error (${response.status})`,
      response.status
    );
  }

  return await response.json();
}

export async function fetchCurrentUser(
  serverUrl: string,
  authToken: string
): Promise<{ id: string; email: string; display_name: string; api_key: string }> {
  let response: Response;

  try {
    response = await fetch(`${serverUrl}/api/auth/me`, {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${authToken}` },
    });
  } catch (err) {
    throw new SieveApiError('network_error', 'Failed to connect to Neural Sieve');
  }

  if (!response.ok) {
    if (response.status === 401) {
      throw new SieveApiError('auth_expired', 'Session expired', 401);
    }
    throw new SieveApiError('server_error', 'Failed to fetch user info');
  }

  return await response.json();
}
```

**Step 4: Run the test**

```bash
cd extension && npx vitest run tests/sieve-api-client.test.ts
```

Expected: PASS

**Step 5: Delete obsidian-note-creator.ts**

```bash
rm extension/src/utils/obsidian-note-creator.ts
```

This will cause build errors in popup.ts — that's expected, we'll fix those in Task 9.

**Step 6: Commit**

```bash
git add extension/src/utils/sieve-api-client.ts extension/tests/sieve-api-client.test.ts
git rm extension/src/utils/obsidian-note-creator.ts
git commit -m "feat: add Neural Sieve API client, remove obsidian-note-creator"
```

---

## Task 7: Remove Interpreter feature

**Files:**
- Delete: `extension/src/managers/interpreter-settings.ts`
- Modify: `extension/src/core/settings.ts`
- Modify: `extension/src/core/popup.ts`
- Modify: `extension/src/settings.html`
- Modify: `extension/src/utils/storage-utils.ts`

**Step 1: Delete the interpreter settings manager**

```bash
rm extension/src/managers/interpreter-settings.ts
```

**Step 2: Remove interpreter imports and calls from settings.ts**

In `extension/src/core/settings.ts`:
- Remove import of `initializeInterpreterSettings` (or similar)
- Remove the call to initialize interpreter settings
- Remove the interpreter tab/section from the settings UI initialization

**Step 3: Remove interpreter from popup.ts**

In `extension/src/core/popup.ts`:
- Remove imports related to interpreter (`interpreter.ts`, prompt variables, etc.)
- Remove the interpreter section toggle and execution logic
- In `handleClipObsidian()` (or its replacement), remove the block that checks `interpreterEnabled` and runs prompt variables through the interpreter before saving

**Step 4: Remove interpreter UI from settings.html**

In `extension/src/settings.html`:
- Remove the interpreter settings section (the sidebar nav item and the content section)

**Step 5: Remove interpreter references from popup.html**

In `extension/src/popup.html`:
- Remove the `#interpreter` div

**Step 6: Clean up storage-utils**

Already done in Task 5 (removed interpreter-related defaults), but verify no references remain.

**Step 7: Verify build**

```bash
cd extension && npm run build:chrome
```

Fix any remaining import errors. The `src/utils/interpreter.ts` file can be kept for now if other parts reference it (template prompt variables) — but if prompt variables are only used by the interpreter, remove `src/utils/interpreter.ts` too.

If template prompt variables (`{{"natural language prompt"}}` syntax) depend on the interpreter, remove that variable type from the template compiler as well, since the server-side LLM handles everything.

**Step 8: Commit**

```bash
git add -A extension/
git commit -m "feat: remove LLM Interpreter feature (server handles extraction)"
```

---

## Task 8: Add login UI to popup

**Files:**
- Modify: `extension/src/popup.html`
- Modify: `extension/src/core/popup.ts`

**Step 1: Replace vault selector with login section in popup.html**

In `extension/src/popup.html`, replace the vault-path-container area:

```html
<!-- Replace the vault-path-container with auth section -->
<div id="auth-section">
  <!-- Logged out state -->
  <div id="auth-login" style="display: none;">
    <div class="auth-form">
      <input id="login-email" type="email" placeholder="Email" class="auth-input" />
      <input id="login-password" type="password" placeholder="Password" class="auth-input" />
      <div class="auth-actions">
        <button id="login-btn" class="mod-cta">Sign In</button>
        <a id="signup-link" class="auth-link">Create account</a>
      </div>
      <p id="login-error" class="error-message" style="display: none;"></p>
    </div>
  </div>
  <!-- Logged in state -->
  <div id="auth-user" style="display: none;">
    <div class="auth-user-info">
      <span id="auth-username"></span>
      <a id="logout-link" class="auth-link">Log out</a>
    </div>
  </div>
</div>
```

Remove the `#vault-container`, `#vault-select`, and `#path-name-field` elements.
Remove the `#interpreter` div.
Remove the `#note-name-field` textarea (server generates the title).

**Step 2: Add auth logic to popup.ts**

In `extension/src/core/popup.ts`:

Remove:
- `updateVaultDropdown()` function and calls
- `lastSelectedVault` state
- Vault-related event listeners

Add auth functions:

```typescript
import { loginToSieve, fetchCurrentUser, SieveApiError } from '../utils/sieve-api-client';
import { generalSettings, saveSettings } from '../utils/storage-utils';

async function initializeAuth(): Promise<void> {
  const loginSection = document.getElementById('auth-login')!;
  const userSection = document.getElementById('auth-user')!;

  if (generalSettings.authToken && generalSettings.authUser) {
    // Show logged-in state
    loginSection.style.display = 'none';
    userSection.style.display = 'flex';
    const usernameEl = document.getElementById('auth-username')!;
    usernameEl.textContent =
      generalSettings.authUser.displayName || generalSettings.authUser.email;
  } else {
    // Show login form
    loginSection.style.display = 'block';
    userSection.style.display = 'none';
  }
}

function setupAuthListeners(): void {
  document.getElementById('login-btn')?.addEventListener('click', handleLogin);
  document.getElementById('login-password')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleLogin();
  });
  document.getElementById('logout-link')?.addEventListener('click', handleLogout);
  document.getElementById('signup-link')?.addEventListener('click', () => {
    browser.tabs.create({ url: `${generalSettings.serverUrl}/signup` });
  });
}

async function handleLogin(): Promise<void> {
  const emailInput = document.getElementById('login-email') as HTMLInputElement;
  const passwordInput = document.getElementById('login-password') as HTMLInputElement;
  const errorEl = document.getElementById('login-error')!;
  const loginBtn = document.getElementById('login-btn') as HTMLButtonElement;

  const email = emailInput.value;
  const password = passwordInput.value;

  if (!email || !password) {
    errorEl.textContent = 'Please enter email and password';
    errorEl.style.display = 'block';
    return;
  }

  loginBtn.disabled = true;
  loginBtn.textContent = 'Signing in...';
  errorEl.style.display = 'none';

  try {
    const { access_token } = await loginToSieve(generalSettings.serverUrl, email, password);
    const user = await fetchCurrentUser(generalSettings.serverUrl, access_token);

    generalSettings.authToken = access_token;
    generalSettings.authUser = {
      email: user.email,
      username: '',
      displayName: user.display_name,
    };
    await saveSettings();
    await initializeAuth();
  } catch (err) {
    if (err instanceof SieveApiError) {
      errorEl.textContent = err.message;
    } else {
      errorEl.textContent = 'Connection failed. Check your server URL.';
    }
    errorEl.style.display = 'block';
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'Sign In';
  }
}

async function handleLogout(): Promise<void> {
  generalSettings.authToken = null;
  generalSettings.authUser = null;
  await saveSettings();
  await initializeAuth();
}
```

Call `initializeAuth()` and `setupAuthListeners()` in the DOMContentLoaded handler (where `updateVaultDropdown()` used to be).

**Step 3: Disable save button when not authenticated**

In the `determineMainAction()` function, if `!generalSettings.authToken`, disable the save button and show "Sign in to capture".

**Step 4: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 5: Commit**

```bash
git add extension/src/popup.html extension/src/core/popup.ts
git commit -m "feat: add login UI to popup, replace vault selector"
```

---

## Task 9: Rewire popup save flow to API

**Files:**
- Modify: `extension/src/core/popup.ts`

**Step 1: Replace handleClipObsidian with handleCaptureToSieve**

In `extension/src/core/popup.ts`, replace the `handleClipObsidian()` function:

```typescript
import { captureToSieve, SieveApiError } from '../utils/sieve-api-client';

async function handleCaptureToSieve(): Promise<void> {
  if (!generalSettings.authToken) {
    showError('Please sign in first');
    return;
  }

  const clipBtn = document.getElementById('clip-btn') as HTMLButtonElement;
  clipBtn.disabled = true;
  clipBtn.textContent = 'Capturing...';

  try {
    // Get the compiled template content (note-content-field textarea value)
    const contentField = document.getElementById('note-content-field') as HTMLTextAreaElement;
    const content = contentField?.value || '';

    // Get the page URL from the current tab
    const tabInfo = await browser.runtime.sendMessage({ action: 'getTabInfo' });
    const pageUrl = tabInfo?.url || '';

    const response = await captureToSieve(
      generalSettings.serverUrl,
      generalSettings.authToken,
      {
        content: content,
        url: pageUrl,
        source_url: pageUrl,
      }
    );

    // Success — show toast via content script
    const activeTab = await browser.tabs.query({ active: true, currentWindow: true });
    if (activeTab[0]?.id) {
      await browser.tabs.sendMessage(activeTab[0].id, {
        action: 'showSieveToast',
        title: response.title,
        capsuleId: response.id,
        serverUrl: generalSettings.serverUrl,
      });
    }

    // Update stats
    incrementStat('capture', undefined, undefined, pageUrl, response.title);

    // Close popup (unless side panel)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('context') !== 'iframe' && urlParams.get('context') !== 'side-panel') {
      window.close();
    } else {
      clipBtn.textContent = 'Captured!';
      setTimeout(() => {
        clipBtn.textContent = 'Capture to Sieve';
        clipBtn.disabled = false;
      }, 2000);
    }
  } catch (err) {
    clipBtn.disabled = false;
    clipBtn.textContent = 'Capture to Sieve';

    if (err instanceof SieveApiError) {
      if (err.code === 'auth_expired') {
        generalSettings.authToken = null;
        generalSettings.authUser = null;
        await saveSettings();
        await initializeAuth();
        showError('Session expired. Please sign in again.');
      } else {
        showError(err.message);
      }
    } else {
      showError('Capture failed. Please try again.');
    }
  }
}
```

**Step 2: Update determineMainAction**

Replace the primary action setup:

```typescript
function determineMainAction(): void {
  const clipBtn = document.getElementById('clip-btn') as HTMLButtonElement;

  if (!generalSettings.authToken) {
    clipBtn.textContent = 'Sign in to capture';
    clipBtn.disabled = true;
    return;
  }

  const saveBehavior = generalSettings.saveBehavior || 'captureToSieve';

  if (saveBehavior === 'captureToSieve') {
    clipBtn.textContent = 'Capture to Sieve';
    clipBtn.onclick = () => handleCaptureToSieve();
  } else if (saveBehavior === 'copyToClipboard') {
    clipBtn.textContent = 'Copy to clipboard';
    clipBtn.onclick = () => copyToClipboard(/* compiled content */);
  } else if (saveBehavior === 'saveFile') {
    clipBtn.textContent = 'Save as file';
    clipBtn.onclick = () => handleSaveToDownloads();
  }

  // Set up secondary actions in the dropdown
  const secondaryActions = document.querySelector('.secondary-actions');
  if (secondaryActions) {
    secondaryActions.textContent = ''; // Clear existing children safely
    const actions = [
      { behavior: 'captureToSieve', label: 'Capture to Sieve', handler: handleCaptureToSieve },
      { behavior: 'copyToClipboard', label: 'Copy to clipboard', handler: () => copyToClipboard(/* content */) },
      { behavior: 'saveFile', label: 'Save as file', handler: handleSaveToDownloads },
    ].filter(a => a.behavior !== saveBehavior);

    for (const action of actions) {
      const div = document.createElement('div');
      div.className = 'menu-action';
      div.textContent = action.label;
      div.addEventListener('click', () => action.handler());
      secondaryActions.appendChild(div);
    }
  }
}
```

**Step 3: Update quick clip handler**

Find the message listener for `"triggerQuickClip"` and change it to call `handleCaptureToSieve()` instead of `handleClipObsidian()`.

**Step 4: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 5: Commit**

```bash
git add extension/src/core/popup.ts
git commit -m "feat: rewire popup save flow to Neural Sieve API"
```

---

## Task 10: Add toast notification content script

**Files:**
- Modify: `extension/src/content.ts`

**Step 1: Add toast message handler to content.ts**

In `extension/src/content.ts`, add a new case inside the existing message listener switch/if chain:

```typescript
case 'showSieveToast': {
  const { title, capsuleId, serverUrl } = typedRequest;
  showSieveToast(title, capsuleId, serverUrl);
  break;
}

case 'showSieveErrorToast': {
  showSieveErrorToast(typedRequest.message);
  break;
}
```

Add the toast function using safe DOM construction (no innerHTML):

```typescript
function showSieveToast(title: string, capsuleId: string, serverUrl: string): void {
  // Remove existing toast if any
  const existing = document.getElementById('sieve-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'sieve-toast';
  toast.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 2147483647;
    background: #1a1a2e;
    color: #e0e0e0;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 16px 20px;
    max-width: 360px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    line-height: 1.4;
    cursor: pointer;
    transition: opacity 0.3s, transform 0.3s;
    opacity: 0;
    transform: translateY(10px);
  `;

  // Build toast content using safe DOM methods (no innerHTML)
  const headerEl = document.createElement('div');
  headerEl.style.cssText = 'font-weight: 600; margin-bottom: 4px; color: #7c6bf5;';
  headerEl.textContent = 'Saved to your Sieve';

  const titleEl = document.createElement('div');
  titleEl.style.cssText = 'color: #ccc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';
  titleEl.textContent = title;

  toast.appendChild(headerEl);
  toast.appendChild(titleEl);

  toast.addEventListener('click', () => {
    window.open(`${serverUrl}/capsule/${encodeURIComponent(capsuleId)}`, '_blank');
    toast.remove();
  });

  document.body.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });

  // Auto-dismiss after 4 seconds
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function showSieveErrorToast(message: string): void {
  const existing = document.getElementById('sieve-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'sieve-toast';
  toast.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 2147483647;
    background: #2e1a1a;
    color: #e0e0e0;
    border: 1px solid #4a2020;
    border-radius: 12px;
    padding: 16px 20px;
    max-width: 360px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    line-height: 1.4;
    transition: opacity 0.3s, transform 0.3s;
    opacity: 0;
    transform: translateY(10px);
  `;

  // Build error toast content using safe DOM methods (no innerHTML)
  const headerEl = document.createElement('div');
  headerEl.style.cssText = 'font-weight: 600; margin-bottom: 4px; color: #f55;';
  headerEl.textContent = 'Capture failed';

  const messageEl = document.createElement('div');
  messageEl.style.cssText = 'color: #ccc;';
  messageEl.textContent = message;

  toast.appendChild(headerEl);
  toast.appendChild(messageEl);

  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    setTimeout(() => toast.remove(), 300);
  }, 5000);
}
```

**Step 2: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 3: Commit**

```bash
git add extension/src/content.ts
git commit -m "feat: add toast notifications for capture success and failure"
```

---

## Task 11: Implement quick capture in background script

**Files:**
- Modify: `extension/src/background.ts`

**Step 1: Replace openObsidianUrl handler with capturePageToSieve handler**

In `extension/src/background.ts`, find the `openObsidianUrl` handler (around line 333) and replace it:

```typescript
// Remove the openObsidianUrl handler entirely.

// Add capturePageToSieve handler:

if (typedRequest.action === "capturePageToSieve") {
  const { authToken, serverUrl } = typedRequest;

  try {
    // Get active tab
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    if (!tab?.id) throw new Error('No active tab');

    // Ensure content script is loaded
    await ensureContentScriptLoadedInBackground(tab.id);

    // Extract page content
    const pageContent = await browser.tabs.sendMessage(tab.id, { action: 'getPageContent' });

    // Get markdown content
    const content = pageContent?.content || pageContent?.extractedContent?.content || '';
    const url = tab.url || '';

    // POST to API
    const response = await fetch(`${serverUrl}/api/capture/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`,
      },
      body: JSON.stringify({ content, url, source_url: url }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: 'Unknown error' }));
      if (response.status === 401) {
        await browser.tabs.sendMessage(tab.id, {
          action: 'showSieveErrorToast',
          message: 'Session expired. Please sign in.',
        });
        return { success: false, error: 'auth_expired' };
      }
      await browser.tabs.sendMessage(tab.id, {
        action: 'showSieveErrorToast',
        message: body.detail || 'Capture failed',
      });
      return { success: false, error: body.detail };
    }

    const capsule = await response.json();

    // Show success toast
    await browser.tabs.sendMessage(tab.id, {
      action: 'showSieveToast',
      title: capsule.title,
      capsuleId: capsule.id,
      serverUrl: serverUrl,
    });

    return { success: true, capsule };
  } catch (err: any) {
    // Try to show error toast
    try {
      const tabs = await browser.tabs.query({ active: true, currentWindow: true });
      if (tabs[0]?.id) {
        await browser.tabs.sendMessage(tabs[0].id, {
          action: 'showSieveErrorToast',
          message: err.message || 'Capture failed',
        });
      }
    } catch { /* ignore toast failure */ }
    return { success: false, error: err.message };
  }
}
```

**Step 2: Add browser action click listener for quick mode**

At the top of background.ts, after service worker initialization:

```typescript
// Set popup based on capture mode
async function updatePopupMode(): Promise<void> {
  const stored = await browser.storage.sync.get('general_settings');
  const settings = stored.general_settings || {};
  if (settings.captureMode === 'quick') {
    browser.action.setPopup({ popup: '' });
  } else {
    browser.action.setPopup({ popup: 'popup.html' });
  }
}

updatePopupMode();

// Listen for settings changes to update popup mode
browser.storage.onChanged.addListener((changes) => {
  if (changes.general_settings) {
    updatePopupMode();
  }
});

// browser.action.onClicked fires only when popup is empty (quick mode)
browser.action.onClicked.addListener(async (tab) => {
  const stored = await browser.storage.sync.get('general_settings');
  const settings = stored.general_settings || {};

  if (settings.authToken) {
    browser.runtime.sendMessage({
      action: 'capturePageToSieve',
      authToken: settings.authToken,
      serverUrl: settings.serverUrl || 'https://app.neuralsieve.com',
    });
  } else {
    // Not logged in — temporarily show popup for login
    browser.action.setPopup({ popup: 'popup.html' });
    browser.action.openPopup();
    setTimeout(() => {
      if (settings.captureMode === 'quick') {
        browser.action.setPopup({ popup: '' });
      }
    }, 1000);
  }
});
```

**Step 3: Update the quick_clip command handler**

Find the `quick_clip` command handler and update it to trigger background capture:

```typescript
if (command === 'quick_clip') {
  const stored = await browser.storage.sync.get('general_settings');
  const settings = stored.general_settings || {};
  if (settings.authToken) {
    browser.runtime.sendMessage({
      action: 'capturePageToSieve',
      authToken: settings.authToken,
      serverUrl: settings.serverUrl || 'https://app.neuralsieve.com',
    });
  } else {
    browser.action.openPopup();
  }
}
```

**Step 4: Update context menu handlers**

Update context menu creation to use "Capture" instead of "Clip":

```typescript
browser.contextMenus.create({
  id: 'capture-page',
  title: getMessage('contextMenuCapturePage') || 'Capture page to Sieve',
  contexts: ['page'],
});

browser.contextMenus.create({
  id: 'capture-selection',
  title: getMessage('contextMenuCaptureSelection') || 'Capture selection to Sieve',
  contexts: ['selection'],
});
```

Update the click handler to route `capture-page` to `capturePageToSieve`.

**Step 5: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 6: Commit**

```bash
git add extension/src/background.ts
git commit -m "feat: implement quick capture mode and API capture in background script"
```

---

## Task 12: Update settings page

**Files:**
- Modify: `extension/src/settings.html`
- Modify: `extension/src/managers/general-settings.ts`
- Modify: `extension/src/core/settings.ts`

**Step 1: Add account section to settings.html**

In `extension/src/settings.html`, add a sidebar nav item and content section:

Sidebar nav item:
```html
<div class="nav-item" data-section="account">Account</div>
```

Content section:
```html
<div class="settings-section" id="account-section" style="display: none;">
  <h2>Account</h2>
  <div class="setting-item">
    <label>Server URL</label>
    <input id="server-url-input" type="url" class="setting-input" placeholder="https://app.neuralsieve.com" />
  </div>
  <div id="account-logged-in" style="display: none;">
    <div class="setting-item">
      <label>Signed in as</label>
      <span id="settings-user-email"></span>
    </div>
    <button id="settings-logout-btn" class="mod-warning">Log out</button>
  </div>
  <div id="account-logged-out" style="display: none;">
    <p>Not signed in. Use the extension popup to sign in.</p>
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

**Step 2: Remove vault section from general settings**

In `extension/src/settings.html`, remove the vault management section (vault list, add vault input).

Remove the interpreter section (sidebar nav item and content area) — if not already done in Task 7.

**Step 3: Update general-settings.ts**

In `extension/src/managers/general-settings.ts`:

Remove:
- `updateVaultList()`, `addVault()`, `removeVault()` functions
- Vault input initialization
- `legacyMode` toggle
- `silentOpen` toggle

Add `initializeAccountSettings()`:

```typescript
function initializeAccountSettings(): void {
  const serverUrlInput = document.getElementById('server-url-input') as HTMLInputElement;
  const captureModeSelect = document.getElementById('capture-mode-select') as HTMLSelectElement;
  const loggedIn = document.getElementById('account-logged-in')!;
  const loggedOut = document.getElementById('account-logged-out')!;

  if (serverUrlInput) {
    serverUrlInput.value = generalSettings.serverUrl;
  }
  if (captureModeSelect) {
    captureModeSelect.value = generalSettings.captureMode;
  }

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
    generalSettings.authToken = null;
    generalSettings.authUser = null;
    await saveSettings();
    initializeAccountSettings();
  });
}
```

Call `initializeAccountSettings()` from `initializeGeneralSettings()`.

**Step 4: Update save behavior dropdown**

In `initializeSaveBehaviorDropdown()`, change the default option from `addToObsidian` to `captureToSieve`, and update option labels.

**Step 5: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 6: Commit**

```bash
git add extension/src/settings.html extension/src/managers/general-settings.ts extension/src/core/settings.ts
git commit -m "feat: add account settings, remove vault and interpreter settings sections"
```

---

## Task 13: Generate placeholder icons

**Files:**
- Create/replace: `extension/src/icons/` (icon-16.png, icon-32.png, icon-48.png, icon-128.png)

**Step 1: Create simple placeholder icons**

Use a script or tool to generate simple PNG icons. If ImageMagick is available:

```bash
cd extension/src/icons
convert -size 128x128 xc:'#7c6bf5' -fill white -gravity center -pointsize 80 -annotate 0 'S' icon-128.png
convert icon-128.png -resize 48x48 icon-48.png
convert icon-128.png -resize 32x32 icon-32.png
convert icon-128.png -resize 16x16 icon-16.png
```

If no ImageMagick, create minimal placeholder PNGs using any available approach. The important thing is that they exist and are different from the Obsidian icons.

Update the manifest icon paths if they differ from what was there before.

**Step 2: Verify build**

```bash
cd extension && npm run build:chrome
```

**Step 3: Commit**

```bash
git add extension/src/icons/
git commit -m "chore: add placeholder Sieve Clipper icons"
```

---

## Task 14: Clean up dead code and fix build errors

**Files:**
- Various files in `extension/src/`

**Step 1: Fix all remaining build errors**

Run the build and fix any remaining TypeScript/webpack errors:

```bash
cd extension && npm run build:chrome 2>&1
```

Common issues to fix:
- Import references to deleted files (`obsidian-note-creator`, `interpreter-settings`)
- Type errors from removed fields in `Settings` interface
- Missing function references where `handleClipObsidian` was renamed to `handleCaptureToSieve`
- Template behavior references that no longer exist

**Step 2: Remove any remaining Obsidian-specific dead code**

Search for and clean up:

```bash
cd extension && grep -r "obsidian://" src/ --include="*.ts" --include="*.html"
cd extension && grep -r "openObsidianUrl" src/ --include="*.ts"
cd extension && grep -r "saveToObsidian" src/ --include="*.ts"
```

Remove or update any remaining references.

**Step 3: Run tests**

```bash
cd extension && npm test
```

Fix any test failures. Some existing tests may reference removed types or functions.

**Step 4: Run all browser builds**

```bash
cd extension && npm run build
```

This runs `build:chrome && build:firefox && build:safari`. All three should succeed.

**Step 5: Commit**

```bash
git add -A extension/
git commit -m "fix: clean up dead code, fix all build errors and tests"
```

---

## Task 15: Final verification

**Files:**
- No new files

**Step 1: Build all browsers**

```bash
cd extension && npm run build
```

Expected: All three browser builds succeed.

**Step 2: Run all tests**

```bash
cd extension && npm test
```

Expected: All tests pass.

**Step 3: Verify the Python backend tests still pass**

```bash
cd /Users/lucasfischer/Documents/Code/neural-sieve-v3 && uv run pytest --tb=short -q
```

Expected: All backend tests pass (extension is independent).

**Step 4: Commit**

```bash
git add -A extension/
git commit -m "test: all extension builds and tests passing"
```

---

## Summary

| Task | What's Delivered |
|------|-----------------|
| **1. Fork setup** | Obsidian Clipper copied to `extension/`, builds successfully |
| **2. Rebrand manifests** | All 3 browser manifests updated with Sieve Clipper names |
| **3. Rebrand English locale** | English strings updated, HTML files rebranded |
| **4. Rebrand all locales** | All 35 language files updated |
| **5. Auth types + storage** | Types updated, storage defaults changed, Obsidian fields removed |
| **6. API client** | `sieve-api-client.ts` with capture, login, fetchUser — tested |
| **7. Remove Interpreter** | Interpreter settings and UI completely removed |
| **8. Login UI** | Popup shows login form or username, auth flow works |
| **9. Rewire save flow** | Popup "Capture to Sieve" button POSTs to API |
| **10. Toast notifications** | Success/error toasts injected into page (safe DOM, no innerHTML) |
| **11. Quick capture** | Background script handles one-click capture, context menus rebranded |
| **12. Settings page** | Account section with server URL, capture mode, logout |
| **13. Placeholder icons** | Simple Sieve Clipper icons |
| **14. Clean up** | All dead code removed, all builds passing |
| **15. Final verification** | All extension + backend tests green |

Total: **15 tasks** with exact code, file paths, and verification steps.
