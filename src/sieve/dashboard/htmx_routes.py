import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import create_access_token, get_current_user, hash_password, verify_password
from sieve.api.auth.routes import COOKIE_NAME, set_auth_cookie
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CaptureRequest
from sieve.api.capture.pipeline import CapturePipeline
from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, User

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")


# ---------------------------------------------------------------------------
# Shared dependencies
# ---------------------------------------------------------------------------


async def get_user_sieve(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Sieve:
    """Resolve the authenticated user's sieve, or 404."""
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sieve not found")
    return sieve


async def _get_capsule_or_404(capsule_id: str, sieve: Sieve, db: AsyncSession) -> Capsule:
    """Load a capsule belonging to the given sieve, or raise 404."""
    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()
    if not capsule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capsule not found")
    return capsule


def _render_partial(name: str, **ctx) -> HTMLResponse:
    """Render a Jinja2 partial template and return an HTMLResponse."""
    html = templates.get_template(name).render(**ctx)
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Auth routes (HTMX form submissions)
# ---------------------------------------------------------------------------


@router.post("/auth/login", response_class=HTMLResponse)
async def htmx_login(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")

    if not email or not password:
        return _render_partial("partials/auth_message.html", error="Email and password are required")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        return _render_partial("partials/auth_message.html", error="Invalid email or password")

    token = create_access_token(str(user.id))
    response = _render_partial("partials/auth_message.html", success="Login successful! Redirecting...")
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    response.headers["HX-Redirect"] = "/sieve"
    return response


@router.post("/auth/signup", response_class=HTMLResponse)
async def htmx_signup(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")
    display_name = form.get("display_name", "")
    username = form.get("username", "").strip().lower()

    if not email or not password or not display_name or not username:
        return _render_partial("partials/auth_message.html", error="All fields are required")

    if not re.match(r"^[a-z0-9_]{3,50}$", username):
        return _render_partial(
            "partials/auth_message.html",
            error="Username must be 3-50 characters, lowercase alphanumeric and underscores only",
        )

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        return _render_partial("partials/auth_message.html", error="Email already registered")

    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        return _render_partial("partials/auth_message.html", error="Username already taken")

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        username=username,
    )
    db.add(user)
    sieve = Sieve(user_id=user.id, name=f"{display_name}'s Sieve")
    db.add(sieve)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    response = _render_partial(
        "partials/auth_message.html", success="Account created! Redirecting..."
    )
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    response.headers["HX-Redirect"] = "/sieve"
    return response


@router.post("/auth/logout", response_class=HTMLResponse)
async def htmx_logout():
    response = HTMLResponse(content="")
    response.delete_cookie(key=COOKIE_NAME, path="/")
    response.headers["HX-Redirect"] = "/login"
    return response


# ---------------------------------------------------------------------------
# Capsule routes
# ---------------------------------------------------------------------------


@router.get("/capsules/", response_class=HTMLResponse)
async def htmx_list_capsules(
    request: Request,
    search: str | None = Query(None),
    category: str | None = Query(None),
    domain: str | None = Query(None),
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
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
    return _render_partial("partials/capsule_grid.html", capsules=capsule_dicts)


@router.post("/capture/", response_class=HTMLResponse)
async def htmx_capture(
    request: Request,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    url = form.get("url") or None
    content = form.get("content", "")

    capture_req = CaptureRequest(content=content, url=url)

    pipeline = CapturePipeline()
    try:
        capsule_data = await pipeline.process(capture_req)
    except ValueError as e:
        return _render_partial("partials/capture_result.html", error=str(e))
    except Exception:
        return _render_partial("partials/capture_result.html", error="An unexpected error occurred while processing your content. Please try again.")

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
    return _render_partial("partials/capture_result.html", capsule=resp.model_dump())


@router.put("/capsules/{capsule_id}", response_class=HTMLResponse)
async def htmx_update_capsule(
    request: Request,
    capsule_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    capsule = await _get_capsule_or_404(capsule_id, sieve, db)

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

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/capsule/{capsule_id}"
    return response


@router.delete("/capsules/{capsule_id}", response_class=HTMLResponse)
async def htmx_delete_capsule(
    capsule_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    capsule = await _get_capsule_or_404(capsule_id, sieve, db)

    await db.delete(capsule)
    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = "/sieve"
    return response
