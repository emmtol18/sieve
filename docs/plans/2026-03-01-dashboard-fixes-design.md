# Dashboard Fixes Design

Date: 2026-03-01

Three interconnected fixes: auth flow, HTMX/JSON mismatch, and capture pipeline integration tests.

## 1. Auth Flow (Cookie-Based)

**Problem:** JWT auth exists on the API layer but the dashboard has no token storage, no header injection, no protected routes, and a wrong signup endpoint.

**Solution:** HTTP-only cookies.

- Login/signup endpoints set an `sieve_token` HTTP-only cookie (secure, samesite=lax, path=/, 7-day expiry matching JWT)
- `get_current_user` checks cookie first, falls back to Bearer header (API clients still work)
- Dashboard page routes (`/sieve`, `/capture`, `/discover`, `/compile`, `/capsule/{id}`) get a `require_auth` dependency that redirects to `/login` if no valid cookie
- New `POST /api/auth/logout` clears the cookie
- Fix `login.html` endpoint: `/api/auth/register` -> `/api/auth/signup`

## 2. HTMX Routes Layer (`/htmx/*`)

**Problem:** HTMX templates call `/api/*` JSON endpoints but expect HTML fragments. No bridging layer exists.

**Solution:** New dashboard-specific routes that return Jinja2 partials.

New file: `src/sieve/dashboard/htmx_routes.py`, mounted at `/htmx`.

| HTMX Route | Replaces | Returns |
|---|---|---|
| `POST /htmx/auth/login` | `/api/auth/login` | Sets cookie, HX-Redirect to /sieve |
| `POST /htmx/auth/signup` | `/api/auth/register` | Sets cookie, HX-Redirect to /sieve |
| `GET /htmx/capsules/` | `/api/capsules/` | Capsule grid HTML fragment |
| `POST /htmx/capture/` | `/api/capture/` | Capture result HTML fragment |
| `PUT /htmx/capsules/{id}` | `/api/capsules/{id}` | Updated capsule detail fragment |
| `DELETE /htmx/capsules/{id}` | `/api/capsules/{id}` | Empty + HX-Redirect to /sieve |

New template partials in `src/sieve/dashboard/templates/partials/`:
- `capsule_grid.html` -- grid of capsule cards
- `capsule_card.html` -- single capsule card
- `capture_result.html` -- capture success/error
- `auth_message.html` -- login/signup feedback

All existing templates update `hx-*` attributes to point to `/htmx/*` instead of `/api/*`.

JSON API stays untouched for MCP/external clients.

## 3. Capture Pipeline Integration Tests

**Problem:** No integration tests. Only unit-level schema/model tests exist. No TestClient, no async DB fixtures, no LLM mocking.

**Solution:** Full pipeline + API endpoint integration tests.

New fixtures in `tests/conftest.py`:
- `db_engine` -- async SQLAlchemy engine with in-memory SQLite
- `db_session` -- async session with table create/teardown per test
- `app` -- FastAPI app with overridden DB dependency
- `client` -- httpx.AsyncClient bound to test app
- `auth_cookie` -- creates test user, returns cookie jar with valid `sieve_token`

New test file: `tests/test_capture_integration.py`

Test cases:
1. Capture from text with auth -> 201, capsule in DB
2. Capture from URL (mocked httpx) -> 201, capsule with source_url
3. Capture without auth -> 401
4. Capture with empty content -> 400
5. Capture with localhost URL -> 400 (SSRF)
6. Capture with LLM failure -> 500, no capsule
7. Verify persisted capsule fields match LLM output

Mocking:
- LLM: patch `sieve.llm.client.LLMClient.extract_capsule`
- httpx: patch `sieve.api.capture.scraper.fetch_url`
- DB: real async SQLite in-memory (not mocked)
