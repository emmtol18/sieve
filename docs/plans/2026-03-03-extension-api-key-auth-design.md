# Extension: API Key Auth & Dashboard Theme

**Date:** 2026-03-03
**Status:** Design

## Problem

1. Extension login uses email/password — clunky for a personal tool
2. Extension uses purple accent color, dashboard uses warm cream/orange — visual disconnect
3. No easy way to connect extension to dashboard

## Design

### 1. Backend: API Key Auth Endpoint

Add `GET /api/auth/verify-key` that accepts an API key and returns user info.

**Endpoint:** `GET /api/auth/verify-key`
**Header:** `X-Api-Key: <uuid>`
**Response:** `{ id, email, display_name, api_key }`
**Errors:** 401 if key invalid

Also update `get_token_from_request()` in `deps.py` to check `X-Api-Key` header as a fallback after JWT. This way existing JWT auth keeps working for dashboard, but the extension (and capture endpoint) can use the API key directly.

**Files:**
- `src/sieve/api/auth/routes.py` — add `/verify-key` endpoint
- `src/sieve/api/auth/deps.py` — extend `get_token_from_request` + `get_current_user` to support `X-Api-Key`

### 2. Extension: Replace Email/Password with API Key Input

Replace the `#auth-login` section in `popup.html`:

**Before:**
```html
<input id="login-email" type="email" placeholder="Email" />
<input id="login-password" type="password" placeholder="Password" />
<button id="login-btn">Sign In</button>
<a id="signup-link">Create account</a>
```

**After:**
```html
<input id="login-api-key" type="text" placeholder="Paste your API key" />
<button id="login-btn">Connect</button>
<a id="get-key-link">Get your key from Settings →</a>
<p id="login-error" style="display: none;"></p>
```

The "Get your key from Settings" link opens `{serverUrl}/settings` in a new tab.

**Auth flow:**
1. User pastes API key
2. Extension calls `GET {serverUrl}/api/auth/verify-key` with `X-Api-Key` header
3. On success: store `apiKey` + user info in chrome storage, show logged-in state
4. On failure: show error message

**Storage change:**
- `sieve_auth.authToken` (JWT) → `sieve_auth.apiKey` (UUID)
- All API calls use `X-Api-Key` header instead of `Authorization: Bearer`

**Files:**
- `extension/src/popup.html` — replace auth form
- `extension/src/core/popup.ts` — rewrite `handleLogin`, `setupAuthListeners`, `initializeAuth`
- `extension/src/utils/sieve-api-client.ts` — replace `loginToSieve` with `verifyApiKey`, update `captureToSieve` to use `X-Api-Key`
- `extension/src/utils/storage-utils.ts` — rename `authToken` → `apiKey` in storage schema and Settings type
- `extension/src/types/types.ts` — update Settings interface

### 3. Extension: Dashboard Color Theme

Replace the purple accent variables with the dashboard's warm cream palette.

**Changes to `extension/src/styles/_variables.scss`:**

```scss
:root {
    --accent-h: 22;      /* was 258 (purple) */
    --accent-s: 78%;     /* was 88% */
    --accent-l: 41%;     /* was 66% — maps to ~#c06014 */
}
```

Light mode base colors update to match dashboard:
```
--color-base-00: #faf8f5   (was #ffffff)
--color-base-10: #f5f2ee   (was #fafafa)
--color-base-20: #f0ece7   (was #f6f6f6)
--color-base-30: #e8e4df   (was #e0e0e0)
--color-base-100: #2d2a26  (was #222222)
--color-base-70: #8a857e   (was #5c5c5c)
--color-base-50: #b5b0aa   (was #ababab)
```

This makes `--interactive-accent` resolve to approximately `#c06014` (the dashboard's orange-brown), and all backgrounds/text match the dashboard warm cream feel.

**Files:**
- `extension/src/styles/_variables.scss` — update accent + base color values

### 4. Extension Settings: Simplify Account Section

Update `extension/src/settings.html` account section:
- Remove "Use the extension popup to sign in" text
- When logged out, show the API key input + connect button (same as popup)
- When logged in, show user email + disconnect button

**Files:**
- `extension/src/settings.html` — update account section

## Out of Scope

- Removing password auth from the dashboard (still needed for web login)
- Generating new API key types (keep existing UUID)
- Dark mode for the extension (keep light/dark auto-switching, just change the palette)

## Migration

Existing users with `authToken` stored will be logged out on extension update. They paste their API key once to reconnect. This is acceptable since it's a one-time action.
