# Sieve Clipper — Browser Extension Design

**Date:** 2026-03-02
**Status:** Approved

## Vision

Fork the Obsidian Web Clipper (MIT, ~25K lines TypeScript) and transform it into the Sieve Clipper — a zero-friction knowledge capture extension that POSTs to Neural Sieve's API instead of opening the Obsidian desktop app. Keep the powerful template system, highlighter, reader mode, and multi-browser support. Remove the LLM Interpreter (server handles extraction) and Obsidian-specific features (vault selector, protocol handler, legacy mode).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fork approach | Surgical fork (copy + targeted changes) | Fastest, lowest risk, preserves battle-tested code |
| LLM Interpreter | Remove | Server-side LLM handles all extraction |
| i18n | Keep all 35 languages | International reach, already built |
| Browsers | Chrome + Firefox + Safari | Fork already supports all three |
| Features | Keep all (Highlighter, Reader, Templates) | Already built, differentiates product |
| Auth | Email/password login in popup | Seamless UX, stores JWT in browser storage |
| Location | `extension/` at project root | Clean separation, own build system |

## 1. Save Mechanism Replacement

**Current:** `obsidian-note-creator.ts` builds `obsidian://new?file=...&vault=...` URIs and navigates the browser tab to launch the Obsidian desktop app.

**New:** Replace with `sieve-api-client.ts` that:
1. Takes compiled template output (markdown content + metadata)
2. POSTs to `{serverUrl}/api/capture/` with `{content, url, source_url}`
3. Uses `Authorization: Bearer {jwt}` auth
4. Returns created capsule (title, id) for toast display

**Key files to change:**
- Replace `src/utils/obsidian-note-creator.ts` → `src/utils/sieve-api-client.ts`
- Modify `src/background.ts` — remove `openObsidianUrl` handler, add API call handler
- Modify `src/utils/storage-utils.ts` — add `serverUrl` and `authToken` storage

**Settings impact:** Replace "Vault" config with:
- `serverUrl` (default: production URL, configurable for self-hosted)
- Auth token (stored after login, not user-visible)

## 2. Authentication Flow

**Login UI in popup:**
- When not authenticated: email + password form, "Sign In" button, "Sign Up" link (opens dashboard in new tab)
- When authenticated: username display, small avatar, "Log out" link
- Located where vault selector currently is

**Token management:**
- Login calls `POST {serverUrl}/api/auth/login` → receives JWT
- Stored in `browser.storage.local` (persists across sessions)
- Every capture includes `Authorization: Bearer {token}` header
- On 401 response: clear token, show login UI, toast "Session expired"
- No auto-refresh — tokens last 7 days (server default), user re-logs

**Settings page additions:**
- "Account" section: email, username, server URL
- "Log out" button

## 3. One-Click Capture & Toast

**Two capture modes (user-selectable in settings):**

| Mode | Trigger | Behavior |
|------|---------|----------|
| Quick (default) | Icon click | Instant capture, no popup, shows toast |
| Full | Icon click | Opens popup with template picker, preview, "Save" button |

**Quick mode flow:**
1. `browser.action.onClicked` fires
2. Background script → content script: "extract page"
3. Content script: `defuddle` + Turndown → markdown + URL
4. Background script: POST to `/api/capture/`
5. On success: inject toast into page

**Keyboard shortcuts:**
- `Ctrl+Shift+O` → Quick capture
- `Alt+Shift+O` → Open full popup
- `Alt+Shift+H` → Toggle highlighter
- `Alt+Shift+R` → Toggle reader mode

**Toast notification:**
- Injected as fixed-position element, bottom-right corner
- Shows: "Saved to your Sieve" + capsule title from API response
- Clickable → opens capsule in dashboard
- Auto-dismiss after 4 seconds
- Error toast: "Capture failed" + reason

## 4. Rebranding

**Changed:**
- Name: "Sieve Clipper" (all 35 locale files)
- Description: "Capture knowledge to your Neural Sieve. One click, zero fields."
- Icons: Neural Sieve icons (16, 32, 48, 128px) — placeholder SVGs initially
- Context menu: "Capture to Sieve" / "Capture selection to Sieve"
- Popup/settings headers: "Sieve Clipper" with Neural Sieve branding
- All "Obsidian" user-facing strings → "Sieve" / "Neural Sieve"
- New extension IDs for Chrome Web Store / Firefox Add-ons

**Preserved:**
- MIT license as `LICENSE-obsidian-clipper` (attribution)
- Internal code comments (not worth changing)

**Removed:**
- Vault selector UI and logic
- `obsidian://` protocol handling
- Interpreter settings (LLM provider/model configuration)
- "Open in Obsidian" behavior options
- Legacy mode (clipboard-based transfer)
- Silent open mode

## 5. Template System Adaptation

**Keep:** Template engine (variables, filters, AST rendering), variable picker, filter system, import/export, custom template editor.

**Modify:**
- Remove `behavior` dropdown (no create/append/prepend/overwrite — API always creates capsules)
- Remove vault/path fields from template config
- Remove "Note name" field (server generates capsule title via LLM)
- Default template captures `{{title}}`, `{{content}}`, `{{url}}`, `{{highlighted}}`
- Template output sent as `content` field to `/api/capture/`
- Template properties (YAML frontmatter) become optional metadata hints

## 6. Context Menu, Side Panel & Overlay

**Context menu (right-click):**
- "Capture page to Sieve" — full page capture
- "Capture selection to Sieve" — selected text only

**Side panel (Chrome only):**
- Shows full popup UI docked alongside the page
- Useful for power users wanting to review before sending

**Overlay mode:**
- Iframe-based overlay injected into page
- Keep as-is, rebrand UI text within it

## 7. Architecture

```
+---------------------------+
|     Sieve Clipper          |
|     (Browser Extension)    |
+---------------------------+
|                           |
| content.ts                |  Content script (DOM access)
|   ├── defuddle            |  Content extraction
|   ├── turndown            |  HTML → Markdown
|   └── highlighter         |  Page annotation
|                           |
| background.ts             |  Service worker
|   ├── sieve-api-client    |  POST /api/capture/
|   ├── auth manager        |  JWT storage/refresh
|   └── context menus       |  Right-click integration
|                           |
| popup.ts                  |  Popup UI
|   ├── login form          |  Email/password → JWT
|   ├── template selector   |  Choose capture template
|   ├── content preview     |  Preview before save
|   └── toast trigger       |  Success/error feedback
|                           |
| settings.ts               |  Settings page
|   ├── account section     |  Server URL, logout
|   ├── template manager    |  Create/edit templates
|   ├── highlighter config  |  Colors, behavior
|   └── reader config       |  Font, theme
+---------------------------+
           |
           | POST /api/capture/
           | Authorization: Bearer {jwt}
           | {content, url, source_url}
           v
+---------------------------+
|   Neural Sieve API        |
|   LLM extraction pipeline |
|   → Capsule created       |
+---------------------------+
```

## 8. Build & Development

**Preserved from Obsidian Clipper:**
- Webpack 5 build system
- npm as package manager (TypeScript project, separate from Python backend)
- Multi-browser build targets (`npm run build:chrome/firefox/safari`)
- Vitest test framework
- SCSS styling
- webextension-polyfill for cross-browser compatibility

**Development workflow:**
```bash
cd extension
npm install
npm run dev:chrome    # Watch mode, outputs to dev/
# Load unpacked extension from extension/dev/ in Chrome
```

## 9. What Stays The Same

- Content extraction pipeline (defuddle + turndown)
- Template compiler (variables, filters, AST renderer)
- Highlighter system (per-URL annotations)
- Reader mode (distraction-free reading)
- All 35 language translations (with rebranded strings)
- SCSS design system and dark theme
- Multi-browser manifest generation
- Keyboard shortcuts (rebound to Sieve actions)

## 10. Future (Not In This Design)

- Google OAuth in extension popup (start with email/password)
- Offline capture queue (capture when offline, sync when back)
- Capsule browser in extension sidebar
- Extension-to-dashboard deep links for specific capsule views
- Chrome Web Store / Firefox Add-ons publishing
