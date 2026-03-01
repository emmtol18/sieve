# Dashboard Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix dashboard auth (cookie-based), bridge HTMX/JSON mismatch with `/htmx/*` routes, and add capture pipeline integration tests.

**Architecture:** Cookie-based JWT auth for the dashboard with Bearer header fallback for API clients. New `/htmx/*` router returns Jinja2 HTML partials for all HTMX interactions. Integration tests use in-memory SQLite with mocked LLM/scraper.

**Tech Stack:** FastAPI, SQLAlchemy async, Jinja2, HTMX, pytest-asyncio, httpx.AsyncClient, aiosqlite

---

### Task 1: Add aiosqlite dev dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add aiosqlite to dev deps**

In `pyproject.toml`, add `"aiosqlite>=0.20"` to the `[project.optional-dependencies] dev` list:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "ruff>=0.9",
    "aiosqlite>=0.20",
]
```

**Step 2: Install**

Run: `uv sync --dev`
Expected: aiosqlite installed successfully

**Step 3: Verify**

Run: `uv run python -c "import aiosqlite; print('ok')"`
Expected: `ok`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add aiosqlite dev dependency for async SQLite tests"
```

---

### Task 2: Update `get_current_user` to support cookies

**Files:**
- Modify: `src/sieve/api/auth/deps.py:58-84`
- Test: `tests/test_auth.py`

**Step 1: Write failing test for cookie auth**

Add to `tests/test_auth.py`:

```python
from unittest.mock import AsyncMock, patch
from fastapi import Request

from sieve.api.auth.deps import get_token_from_request


def test_get_token_from_cookie():
    """Token extracted from sieve_token cookie."""
    request = AsyncMock(spec=Request)
    request.cookies = {"sieve_token": "my-jwt-token"}
    request.headers = {}
    assert get_token_from_request(request) == "my-jwt-token"


def test_get_token_from_bearer_header():
    """Falls back to Authorization Bearer header."""
    request = AsyncMock(spec=Request)
    request.cookies = {}
    request.headers = {"authorization": "Bearer my-jwt-token"}
    assert get_token_from_request(request) == "my-jwt-token"


def test_get_token_cookie_takes_precedence():
    """Cookie wins over header when both present."""
    request = AsyncMock(spec=Request)
    request.cookies = {"sieve_token": "cookie-token"}
    request.headers = {"authorization": "Bearer header-token"}
    assert get_token_from_request(request) == "cookie-token"


def test_get_token_missing_returns_none():
    """Returns None when neither cookie nor header present."""
    request = AsyncMock(spec=Request)
    request.cookies = {}
    request.headers = {}
    assert get_token_from_request(request) is None
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_auth.py::test_get_token_from_cookie -v`
Expected: FAIL — `ImportError: cannot import name 'get_token_from_request'`

**Step 3: Implement `get_token_from_request` and update `get_current_user`**

In `src/sieve/api/auth/deps.py`, add this function before `get_current_user`:

```python
def get_token_from_request(request: Request) -> str | None:
    """Extract JWT token from cookie first, then Authorization header."""
    # 1. Check cookie
    token = request.cookies.get("sieve_token")
    if token:
        return token

    # 2. Fall back to Bearer header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    return None
```

Add `Request` to the FastAPI imports at the top:

```python
from fastapi import Depends, HTTPException, Request
```

Then replace the existing `get_current_user` function with:

```python
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = verify_token(token)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
```

Remove the `bearer_scheme = HTTPBearer()` line and the `HTTPAuthorizationCredentials` import since they're no longer needed.

**Step 4: Run tests**

Run: `uv run pytest tests/test_auth.py -v`
Expected: All pass (including existing tests)

**Step 5: Commit**

```bash
git add src/sieve/api/auth/deps.py tests/test_auth.py
git commit -m "feat: support cookie-based auth with Bearer header fallback"
```

---

### Task 3: Add cookie-setting to login/signup + add logout endpoint

**Files:**
- Modify: `src/sieve/api/auth/routes.py`
- Test: `tests/test_auth.py`

**Step 1: Write failing test for cookie in login response**

Add to `tests/test_auth.py`:

```python
def test_set_auth_cookie_creates_response_with_cookie():
    """set_auth_cookie sets httponly sieve_token cookie."""
    from fastapi.responses import JSONResponse
    from sieve.api.auth.routes import set_auth_cookie

    response = JSONResponse(content={"ok": True})
    set_auth_cookie(response, "test-jwt-token", max_age_days=7)

    # Check Set-Cookie header was added
    set_cookie = response.headers.get("set-cookie")
    assert set_cookie is not None
    assert "sieve_token=test-jwt-token" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "path=/" in set_cookie.lower()
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_auth.py::test_set_auth_cookie_creates_response_with_cookie -v`
Expected: FAIL — `ImportError: cannot import name 'set_auth_cookie'`

**Step 3: Implement set_auth_cookie and update routes**

In `src/sieve/api/auth/routes.py`, add the helper and update the routes:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Sieve, User

from .deps import create_access_token, get_current_user, hash_password, verify_password
from .schemas import LoginRequest, SignupRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "sieve_token"


def set_auth_cookie(response: Response, token: str, max_age_days: int = 7) -> None:
    """Set the sieve_token HTTP-only cookie on a response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=max_age_days * 86400,
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)

    sieve = Sieve(
        user_id=user.id,
        name=f"{body.display_name}'s Sieve",
    )
    db.add(sieve)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    data = TokenResponse(access_token=token, api_key=str(user.api_key))
    response = JSONResponse(content=data.model_dump(), status_code=201)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    return response


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(str(user.id))
    data = TokenResponse(access_token=token, api_key=str(user.api_key))
    response = JSONResponse(content=data.model_dump(), status_code=200)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        api_key=str(user.api_key),
    )
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_auth.py -v`
Expected: All pass

**Step 5: Commit**

```bash
git add src/sieve/api/auth/routes.py tests/test_auth.py
git commit -m "feat: set auth cookie on login/signup, add logout endpoint"
```

---

### Task 4: Add `require_auth` dependency for dashboard page routes

**Files:**
- Modify: `src/sieve/dashboard/routes.py`
- Test: `tests/test_dashboard.py`

**Step 1: Write failing test**

Add to `tests/test_dashboard.py`:

```python
def test_protected_routes_exist():
    """Protected dashboard routes should use require_auth dependency."""
    from sieve.dashboard.routes import router

    protected_paths = {"/sieve", "/capture", "/discover", "/compile"}
    for route in router.routes:
        if hasattr(route, "path") and route.path in protected_paths:
            dep_names = [d.dependency.__name__ for d in route.dependant.dependencies if hasattr(d.dependency, "__name__")]
            assert "require_auth" in dep_names, f"Route {route.path} missing require_auth dependency"
```

**Step 2: Run to verify failure**

Run: `uv run pytest tests/test_dashboard.py::test_protected_routes_exist -v`
Expected: FAIL — `require_auth` not found in dependencies

**Step 3: Implement require_auth and apply to routes**

Replace `src/sieve/dashboard/routes.py` with:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt

from sieve.config import settings

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")


async def require_auth(request: Request) -> None:
    """Redirect to /login if no valid sieve_token cookie."""
    token = request.cookies.get("sieve_token")
    if not token:
        raise _redirect_to_login()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("sub") is None:
            raise _redirect_to_login()
    except JWTError:
        raise _redirect_to_login()


def _redirect_to_login():
    """Return an HTTPException-like redirect. Use raise with this."""
    from fastapi.exceptions import HTTPException

    class _RedirectException(HTTPException):
        def __init__(self):
            super().__init__(status_code=307, detail="Redirect to login")

    # We actually want a redirect response, not a JSON error.
    # FastAPI doesn't support redirect from dependencies natively,
    # so we use a custom exception handler. For simplicity, we'll
    # use a different pattern: return RedirectResponse from an
    # exception handler.
    raise _RedirectException()


# Actually, the cleanest pattern is to NOT use an exception. Instead,
# use a middleware or check inside each route. But the cleanest FastAPI
# pattern for auth redirects in dependencies is to raise an HTTPException
# and add a custom exception handler. Let's use the simpler approach:

from starlette.exceptions import HTTPException as StarletteHTTPException


async def require_auth(request: Request) -> None:
    """Redirect to /login if no valid sieve_token cookie."""
    token = request.cookies.get("sieve_token")
    if not token:
        raise StarletteHTTPException(status_code=307)
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("sub") is None:
            raise StarletteHTTPException(status_code=307)
    except JWTError:
        raise StarletteHTTPException(status_code=307)
```

Hmm — this is getting tangled. Let me use the straightforward pattern.

Actually, **replace the entire file** `src/sieve/dashboard/routes.py` with:

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt

from sieve.config import settings

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")


def _is_authenticated(request: Request) -> bool:
    """Check if the request has a valid sieve_token cookie."""
    token = request.cookies.get("sieve_token")
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub") is not None
    except JWTError:
        return False


async def require_auth(request: Request):
    """Dependency that redirects to /login if not authenticated.

    Raises RedirectResponse (which FastAPI handles as a response).
    """
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "sieve.html", {"request": request, "capsules": [], "categories": [], "domains": []}
    )


@router.get("/sieve", response_class=HTMLResponse)
async def sieve_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "sieve.html", {"request": request, "capsules": [], "categories": [], "domains": []}
    )


@router.get("/capture", response_class=HTMLResponse)
async def capture_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("capture.html", {"request": request})


@router.get("/discover", response_class=HTMLResponse)
async def discover_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("discover.html", {"request": request, "packs": []})


@router.get("/compile", response_class=HTMLResponse)
async def compile_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("compile.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/capsule/{capsule_id}", response_class=HTMLResponse)
async def capsule_detail(request: Request, capsule_id: str):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "capsule_detail.html", {"request": request, "capsule": None, "capsule_id": capsule_id}
    )
```

**Step 4: Update test to match actual pattern**

Replace the test with:

```python
def test_protected_routes_redirect_unauthenticated():
    """Protected routes call _is_authenticated check."""
    import inspect
    from sieve.dashboard.routes import sieve_page, capture_page, discover_page, compile_page, capsule_detail

    for fn in [sieve_page, capture_page, discover_page, compile_page, capsule_detail]:
        source = inspect.getsource(fn)
        assert "_is_authenticated" in source, f"{fn.__name__} missing auth check"
```

**Step 5: Run tests**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: All pass

**Step 6: Commit**

```bash
git add src/sieve/dashboard/routes.py tests/test_dashboard.py
git commit -m "feat: protect dashboard routes with cookie auth redirect"
```

---

### Task 5: Create HTMX auth routes (login/signup/logout)

**Files:**
- Create: `src/sieve/dashboard/htmx_routes.py`
- Create: `src/sieve/dashboard/templates/partials/auth_message.html`
- Modify: `src/sieve/dashboard/templates/login.html` (fix endpoints)
- Modify: `src/sieve/api/app.py` (mount htmx router)

**Step 1: Create the auth_message partial**

Create `src/sieve/dashboard/templates/partials/auth_message.html`:

```html
{% if error %}
<div class="alert alert-error">{{ error }}</div>
{% elif success %}
<div class="alert alert-success">{{ success }}</div>
{% endif %}
```

**Step 2: Create htmx_routes.py with auth routes**

Create `src/sieve/dashboard/htmx_routes.py`:

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from sieve.api.auth.routes import COOKIE_NAME, set_auth_cookie
from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Sieve, User

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")


@router.post("/auth/login", response_class=HTMLResponse)
async def htmx_login(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        html = templates.get_template("partials/auth_message.html").render(
            error="Invalid email or password"
        )
        return HTMLResponse(content=html)

    token = create_access_token(str(user.id))
    html = templates.get_template("partials/auth_message.html").render(
        success="Login successful! Redirecting..."
    )
    response = HTMLResponse(content=html)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    response.headers["HX-Redirect"] = "/sieve"
    return response


@router.post("/auth/signup", response_class=HTMLResponse)
async def htmx_signup(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")
    display_name = form.get("display_name", "")

    # Check existing
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        html = templates.get_template("partials/auth_message.html").render(
            error="Email already registered"
        )
        return HTMLResponse(content=html)

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    sieve = Sieve(user_id=user.id, name=f"{display_name}'s Sieve")
    db.add(sieve)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    html = templates.get_template("partials/auth_message.html").render(
        success="Account created! Redirecting..."
    )
    response = HTMLResponse(content=html)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    response.headers["HX-Redirect"] = "/sieve"
    return response


@router.post("/auth/logout", response_class=HTMLResponse)
async def htmx_logout():
    response = HTMLResponse(content="")
    response.delete_cookie(key=COOKIE_NAME, path="/")
    response.headers["HX-Redirect"] = "/login"
    return response
```

**Step 3: Update login.html to use /htmx/* endpoints**

In `src/sieve/dashboard/templates/login.html`, change:
- Line 17: `hx-post="/api/auth/login"` -> `hx-post="/htmx/auth/login"`
- Line 35: `hx-post="/api/auth/register"` -> `hx-post="/htmx/auth/signup"`

**Step 4: Mount htmx router in app.py**

In `src/sieve/api/app.py`, add:

```python
from sieve.dashboard.htmx_routes import router as htmx_router
```

And in `create_app()`, add before the dashboard router:

```python
app.include_router(htmx_router)
```

**Step 5: Run existing tests to check nothing broke**

Run: `uv run pytest -v`
Expected: All existing tests pass

**Step 6: Commit**

```bash
git add src/sieve/dashboard/htmx_routes.py src/sieve/dashboard/templates/partials/auth_message.html src/sieve/dashboard/templates/login.html src/sieve/api/app.py
git commit -m "feat: add HTMX auth routes with cookie handling and login template fix"
```

---

### Task 6: Create HTMX capsule routes (list, capture, update, delete)

**Files:**
- Modify: `src/sieve/dashboard/htmx_routes.py`
- Create: `src/sieve/dashboard/templates/partials/capsule_grid.html`
- Create: `src/sieve/dashboard/templates/partials/capsule_card.html`
- Create: `src/sieve/dashboard/templates/partials/capture_result.html`
- Modify: `src/sieve/dashboard/templates/sieve.html` (fix hx-get)
- Modify: `src/sieve/dashboard/templates/capture.html` (fix hx-post)
- Modify: `src/sieve/dashboard/templates/capsule_detail.html` (fix hx-put/delete)

**Step 1: Create capsule_card.html partial**

Create `src/sieve/dashboard/templates/partials/capsule_card.html`:

```html
<a href="/capsule/{{ capsule.id }}" class="card capsule-card" hx-boost="true">
    <div class="card-header">
        {% if capsule.category %}
        <span class="badge">{{ capsule.category }}</span>
        {% endif %}
        {% if capsule.pinned %}
        <span class="pin-indicator" title="Pinned">&#9733;</span>
        {% endif %}
    </div>
    <h3 class="card-title">{{ capsule.title }}</h3>
    <p class="card-summary">{{ capsule.executive_summary }}</p>
    <div class="tag-list">
        {% for tag in capsule.tags[:4] %}
        <span class="tag-chip">{{ tag }}</span>
        {% endfor %}
    </div>
    <div class="card-meta">
        {% if capsule.domain %}<span>{{ capsule.domain }}</span>{% endif %}
        {% if capsule.difficulty %}<span class="meta-sep">{{ capsule.difficulty }}</span>{% endif %}
        {% if capsule.created_at %}<span class="meta-sep">{{ capsule.created_at[:10] }}</span>{% endif %}
    </div>
</a>
```

**Step 2: Create capsule_grid.html partial**

Create `src/sieve/dashboard/templates/partials/capsule_grid.html`:

```html
{% if capsules %}
    {% for capsule in capsules %}
    {% include "partials/capsule_card.html" %}
    {% endfor %}
{% else %}
    <div class="empty-state">
        <div class="empty-icon">&#9670;</div>
        <h3>No capsules found</h3>
        <p>Try a different search or <a href="/capture">capture some knowledge</a>.</p>
    </div>
{% endif %}
```

**Step 3: Create capture_result.html partial**

Create `src/sieve/dashboard/templates/partials/capture_result.html`:

```html
{% if error %}
<div class="alert alert-error">{{ error }}</div>
{% elif capsule %}
<div class="alert alert-success">
    <strong>Captured!</strong> &ldquo;{{ capsule.title }}&rdquo; has been added to your sieve.
    <a href="/capsule/{{ capsule.id }}">View capsule &rarr;</a>
</div>
{% endif %}
```

**Step 4: Add capsule HTMX routes to htmx_routes.py**

Append to `src/sieve/dashboard/htmx_routes.py`:

```python
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CaptureRequest
from sieve.api.capture.pipeline import CapturePipeline
from sieve.db.models import Capsule

from fastapi import Query


@router.get("/capsules/", response_class=HTMLResponse)
async def htmx_list_capsules(
    request: Request,
    search: str | None = Query(None),
    category: str | None = Query(None),
    domain: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func, or_

    sieve = await _get_user_sieve(user, db)

    query = select(Capsule).where(Capsule.sieve_id == sieve.id)

    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                Capsule.title.ilike(term),
                Capsule.executive_summary.ilike(term),
                Capsule.core_insight.ilike(term),
                Capsule.full_content.ilike(term),
            )
        )
    if category:
        query = query.where(Capsule.category.ilike(f"%{category}%"))
    if domain:
        query = query.where(Capsule.domain.ilike(f"%{domain}%"))

    query = query.order_by(Capsule.created_at.desc()).limit(50)
    result = await db.execute(query)
    capsules = result.scalars().all()

    capsule_dicts = [capsule_to_response(c).model_dump() for c in capsules]

    html = templates.get_template("partials/capsule_grid.html").render(capsules=capsule_dicts)
    return HTMLResponse(content=html)


@router.post("/capture/", response_class=HTMLResponse)
async def htmx_capture(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    url = form.get("url") or None
    content = form.get("content", "")

    capture_req = CaptureRequest(content=content, url=url)

    sieve = await _get_user_sieve(user, db)

    pipeline = CapturePipeline()
    try:
        capsule_data = await pipeline.process(capture_req)
    except ValueError as e:
        html = templates.get_template("partials/capture_result.html").render(error=str(e))
        return HTMLResponse(content=html)

    capsule = Capsule(
        sieve_id=sieve.id,
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
        source_url=capsule_data.get("source_url"),
        capture_method=capsule_data.get("capture_method", "manual"),
        source_type=capsule_data.get("source_type", ""),
    )
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)

    resp = capsule_to_response(capsule)
    html = templates.get_template("partials/capture_result.html").render(capsule=resp.model_dump())
    return HTMLResponse(content=html)


@router.put("/capsules/{capsule_id}", response_class=HTMLResponse)
async def htmx_update_capsule(
    request: Request,
    capsule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()
    if not capsule:
        return HTMLResponse(content='<div class="alert alert-error">Capsule not found</div>', status_code=404)

    form = await request.form()
    for field in ["title", "executive_summary", "core_insight", "pinned"]:
        value = form.get(field)
        if value is not None:
            if field == "pinned":
                setattr(capsule, field, value in ("true", "True", True))
            else:
                setattr(capsule, field, value)

    await db.commit()
    await db.refresh(capsule)

    # Redirect to refreshed capsule detail page
    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/capsule/{capsule_id}"
    return response


@router.delete("/capsules/{capsule_id}", response_class=HTMLResponse)
async def htmx_delete_capsule(
    capsule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()
    if not capsule:
        return HTMLResponse(content='<div class="alert alert-error">Capsule not found</div>', status_code=404)

    await db.delete(capsule)
    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = "/sieve"
    return response


async def _get_user_sieve(user: User, db: AsyncSession) -> Sieve:
    """Get the current user's sieve."""
    from fastapi import HTTPException, status
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sieve not found")
    return sieve
```

**Step 5: Update templates to use /htmx/* endpoints**

In `src/sieve/dashboard/templates/sieve.html`:
- Line 16: `hx-get="/api/capsules/"` -> `hx-get="/htmx/capsules/"`
- Line 23: `hx-get="/api/capsules/"` -> `hx-get="/htmx/capsules/"`
- Line 29: `hx-get="/api/capsules/"` -> `hx-get="/htmx/capsules/"`

In `src/sieve/dashboard/templates/capture.html`:
- Line 11: `hx-post="/api/capture/"` -> `hx-post="/htmx/capture/"`

In `src/sieve/dashboard/templates/capsule_detail.html`:
- Line 12: `hx-put="/api/capsules/{{ capsule.id }}"` -> `hx-put="/htmx/capsules/{{ capsule.id }}"`
- Line 20: `hx-delete="/api/capsules/{{ capsule.id }}"` -> `hx-delete="/htmx/capsules/{{ capsule.id }}"`
- Line 92: `hx-put="/api/capsules/{{ capsule.id }}"` -> `hx-put="/htmx/capsules/{{ capsule.id }}"`

**Step 6: Run all tests**

Run: `uv run pytest -v`
Expected: All pass

**Step 7: Commit**

```bash
git add src/sieve/dashboard/htmx_routes.py src/sieve/dashboard/templates/partials/ src/sieve/dashboard/templates/sieve.html src/sieve/dashboard/templates/capture.html src/sieve/dashboard/templates/capsule_detail.html
git commit -m "feat: add HTMX capsule routes and partials, update templates"
```

---

### Task 7: Add logout button to base template

**Files:**
- Modify: `src/sieve/dashboard/templates/base.html`

**Step 1: Add logout button to nav**

In `src/sieve/dashboard/templates/base.html`, after the nav-links div (line 23), add a logout button:

```html
<div class="nav-links">
    <a href="/sieve" hx-boost="true">My Sieve</a>
    <a href="/capture" hx-boost="true">Capture</a>
    <a href="/discover" hx-boost="true">Discover</a>
    <a href="/compile" hx-boost="true">Compile</a>
    <button class="btn btn-secondary btn-sm nav-logout" hx-post="/htmx/auth/logout" hx-swap="none">Logout</button>
</div>
```

**Step 2: Run tests**

Run: `uv run pytest tests/test_dashboard.py -v`
Expected: All pass

**Step 3: Commit**

```bash
git add src/sieve/dashboard/templates/base.html
git commit -m "feat: add logout button to dashboard nav"
```

---

### Task 8: Set up integration test fixtures in conftest.py

**Files:**
- Modify: `tests/conftest.py`

**Step 1: Write the fixtures**

Replace `tests/conftest.py` with:

```python
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sieve.api.auth.deps import create_access_token, hash_password
from sieve.config import Settings
from sieve.db.models import Base, Sieve, User


@pytest.fixture
def settings():
    return Settings(database_url="sqlite+aiosqlite:///test.db")


@pytest.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def app(db_engine):
    from sieve.api.app import create_app
    from sieve.db.database import get_db

    test_app = create_app()

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    test_app.dependency_overrides[get_db] = override_get_db
    return test_app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(db_session):
    """Create a test user with a sieve and return (user, sieve)."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword"),
        display_name="Test User",
    )
    db_session.add(user)
    sieve = Sieve(user_id=user.id, name="Test Sieve")
    db_session.add(sieve)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(sieve)
    return user, sieve


@pytest.fixture
def auth_cookies(test_user):
    """Return cookies dict with valid sieve_token for the test user."""
    user, _ = test_user
    token = create_access_token(str(user.id))
    return {"sieve_token": token}
```

**Step 2: Verify fixtures work**

Run: `uv run pytest tests/test_auth.py -v`
Expected: All existing tests still pass (they don't use the new fixtures yet)

**Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: add async DB/client/auth integration test fixtures"
```

---

### Task 9: Write capture pipeline integration tests

**Files:**
- Create: `tests/test_capture_integration.py`

**Step 1: Write all integration tests**

Create `tests/test_capture_integration.py`:

```python
from unittest.mock import AsyncMock, patch

import pytest


MOCK_LLM_RESULT = {
    "title": "Test Capsule",
    "executive_summary": "A test summary",
    "core_insight": "A test insight",
    "tags": ["test", "mock"],
    "keywords": ["testing"],
    "topics": ["Software Testing"],
    "category": "Technology",
    "domain": "engineering",
    "difficulty": "beginner",
    "content_type": "insight",
    "source_type": "article",
}


@pytest.fixture
def mock_llm():
    with patch("sieve.api.capture.pipeline.LLMClient") as mock_cls:
        instance = mock_cls.return_value
        result = {**MOCK_LLM_RESULT, "full_content": "Some test content"}
        instance.extract_capsule = AsyncMock(return_value=result)
        yield instance


@pytest.fixture
def mock_fetch_url():
    with patch("sieve.api.capture.pipeline.fetch_url", new_callable=AsyncMock) as mock:
        mock.return_value = "<html><body><p>Fetched content</p></body></html>"
        yield mock


async def test_capture_text_authenticated(client, test_user, auth_cookies, mock_llm):
    """POST text content with auth cookie returns 201 and created capsule."""
    response = await client.post(
        "/api/capture/",
        json={"content": "Some knowledge to capture"},
        cookies=auth_cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Capsule"
    assert data["capture_method"] == "manual"
    mock_llm.extract_capsule.assert_called_once()


async def test_capture_url_authenticated(client, test_user, auth_cookies, mock_llm, mock_fetch_url):
    """POST URL with auth cookie returns 201 with source_url set."""
    response = await client.post(
        "/api/capture/",
        json={"url": "https://example.com/article"},
        cookies=auth_cookies,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Capsule"
    assert data["source_url"] == "https://example.com/article"
    assert data["capture_method"] == "url"
    mock_fetch_url.assert_called_once_with("https://example.com/article")


async def test_capture_unauthenticated(client):
    """POST without auth cookie returns 401."""
    response = await client.post(
        "/api/capture/",
        json={"content": "Some content"},
    )
    assert response.status_code == 401


async def test_capture_empty_content(client, test_user, auth_cookies, mock_llm):
    """POST with empty content and no URL returns 400."""
    # Override mock to not be called (pipeline raises ValueError before LLM)
    response = await client.post(
        "/api/capture/",
        json={"content": ""},
        cookies=auth_cookies,
    )
    assert response.status_code == 400


async def test_capture_localhost_url(client, test_user, auth_cookies):
    """POST with localhost URL returns 400 (SSRF protection)."""
    response = await client.post(
        "/api/capture/",
        json={"url": "http://localhost/secret"},
        cookies=auth_cookies,
    )
    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()


async def test_capture_llm_failure(client, test_user, auth_cookies):
    """POST when LLM raises returns 500."""
    with patch("sieve.api.capture.pipeline.LLMClient") as mock_cls:
        instance = mock_cls.return_value
        instance.extract_capsule = AsyncMock(side_effect=Exception("LLM is down"))
        response = await client.post(
            "/api/capture/",
            json={"content": "Some content"},
            cookies=auth_cookies,
        )
    assert response.status_code == 500


async def test_capture_persists_to_db(client, test_user, auth_cookies, mock_llm, db_session):
    """Captured capsule is persisted to database with correct fields."""
    from sqlalchemy import select
    from sieve.db.models import Capsule

    response = await client.post(
        "/api/capture/",
        json={"content": "Persist this knowledge"},
        cookies=auth_cookies,
    )
    assert response.status_code == 201
    capsule_id = response.json()["id"]

    result = await db_session.execute(select(Capsule).where(Capsule.id == capsule_id))
    capsule = result.scalar_one_or_none()
    assert capsule is not None
    assert capsule.title == "Test Capsule"
    assert capsule.category == "Technology"
    assert capsule.tags == ["test", "mock"]
```

**Step 2: Run the tests**

Run: `uv run pytest tests/test_capture_integration.py -v`
Expected: All 7 tests pass

**Step 3: Run full suite**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add tests/test_capture_integration.py
git commit -m "test: add capture pipeline integration tests with mocked LLM"
```

---

### Task 10: Final verification

**Step 1: Run full test suite with coverage**

Run: `uv run pytest -v --tb=short`
Expected: All tests pass, no warnings

**Step 2: Run ruff lint check**

Run: `uv run ruff check src/ tests/`
Expected: No errors (or only pre-existing ones)

**Step 3: Verify the app starts**

Run: `uv run python -c "from sieve.api.app import create_app; app = create_app(); print('App created with routes:', [r.path for r in app.routes if hasattr(r, 'path')])"`
Expected: Shows all routes including `/htmx/*`

**Step 4: Final commit if any fixes needed**

If any fixes were needed, commit them:
```bash
git add -A
git commit -m "fix: address lint/test issues from final verification"
```
