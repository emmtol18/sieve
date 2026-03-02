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
from sieve.db.models import Capsule, Follow, Sieve, User

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


# ---------------------------------------------------------------------------
# Feed routes
# ---------------------------------------------------------------------------


def _extract_domain(url: str | None) -> str:
    """Extract domain from a URL, e.g. 'https://example.com/path' -> 'example.com'."""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or ""
    except Exception:
        return ""


async def _capsule_to_feed_dict(capsule: Capsule, db: AsyncSession) -> dict:
    """Convert a Capsule ORM object to a dict suitable for feed_card.html."""
    # Eagerly load the sieve -> user for author info
    result = await db.execute(
        select(Sieve, User)
        .join(User, Sieve.user_id == User.id)
        .where(Sieve.id == capsule.sieve_id)
    )
    row = result.one_or_none()
    author_username = row[1].username if row else None

    return {
        "id": str(capsule.id),
        "title": capsule.title,
        "executive_summary": capsule.executive_summary,
        "core_insight": capsule.core_insight,
        "tags": capsule.tags or [],
        "source_url": capsule.source_url,
        "source_domain": _extract_domain(capsule.source_url),
        "created_at": capsule.created_at.strftime("%Y-%m-%d") if capsule.created_at else "",
        "author_username": author_username,
    }


@router.get("/feed/", response_class=HTMLResponse)
async def htmx_feed(
    filter: str = Query("all"),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get the user's sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        return HTMLResponse(content='<div class="empty-state"><h3>No sieve found</h3></div>')

    if filter == "mine":
        query = select(Capsule).where(Capsule.sieve_id == sieve.id)
    elif filter == "following":
        # Get IDs of sieves we follow
        follow_result = await db.execute(
            select(Follow.followed_sieve_id).where(Follow.follower_sieve_id == sieve.id)
        )
        followed_ids = [row[0] for row in follow_result.all()]
        if not followed_ids:
            return _render_partial(
                "partials/feed_empty.html",
                message="You're not following anyone yet.",
                cta_url="/discover",
                cta_text="Discover sieves to follow",
            )
        query = select(Capsule).where(Capsule.sieve_id.in_(followed_ids))
    else:  # "all" — own + followed
        follow_result = await db.execute(
            select(Follow.followed_sieve_id).where(Follow.follower_sieve_id == sieve.id)
        )
        followed_ids = [row[0] for row in follow_result.all()]
        all_sieve_ids = [sieve.id] + followed_ids
        query = select(Capsule).where(Capsule.sieve_id.in_(all_sieve_ids))

    query = query.order_by(Capsule.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    capsules = result.scalars().all()

    if not capsules:
        empty_html = templates.get_template("partials/feed_empty.html").render(
            message="No capsules yet.",
            cta_url="/capture",
            cta_text="Capture your first knowledge",
        )
        return HTMLResponse(content=empty_html)

    # Build feed card dicts with author info
    feed_items = []
    for c in capsules:
        feed_items.append(await _capsule_to_feed_dict(c, db))

    html_parts = []
    for item in feed_items:
        html_parts.append(templates.get_template("partials/feed_card.html").render(capsule=item))

    return HTMLResponse(content="".join(html_parts))


# ---------------------------------------------------------------------------
# Discover routes
# ---------------------------------------------------------------------------


@router.get("/discover/sieves", response_class=HTMLResponse)
async def htmx_discover_sieves(
    search: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get the current user's sieve for follow status
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    my_sieve = result.scalar_one_or_none()

    query = select(Sieve, User).join(User, Sieve.user_id == User.id).where(Sieve.is_public == True)  # noqa: E712

    if search:
        term = f"%{search}%"
        query = query.where(
            or_(
                User.display_name.ilike(term),
                User.username.ilike(term),
                Sieve.bio.ilike(term),
                Sieve.name.ilike(term),
            )
        )

    query = query.order_by(Sieve.created_at.desc()).limit(50)
    result = await db.execute(query)
    rows = result.all()

    if not rows:
        return HTMLResponse(
            content='<div class="empty-state"><h3>No public sieves found</h3><p>Check back later as more users share their knowledge.</p></div>'
        )

    html_parts = []
    for sieve_obj, user_obj in rows:
        # Get follower and capsule counts
        from sqlalchemy import func

        follower_count_result = await db.execute(
            select(func.count()).where(Follow.followed_sieve_id == sieve_obj.id)
        )
        follower_count = follower_count_result.scalar() or 0

        capsule_count_result = await db.execute(
            select(func.count()).where(Capsule.sieve_id == sieve_obj.id)
        )
        capsule_count = capsule_count_result.scalar() or 0

        # Check if we follow this sieve
        is_following = False
        if my_sieve:
            follow_check = await db.execute(
                select(Follow).where(
                    Follow.follower_sieve_id == my_sieve.id,
                    Follow.followed_sieve_id == sieve_obj.id,
                )
            )
            is_following = follow_check.scalar_one_or_none() is not None

        is_own = my_sieve and sieve_obj.id == my_sieve.id

        card_data = {
            "display_name": user_obj.display_name,
            "username": user_obj.username,
            "bio": sieve_obj.bio or "",
            "follower_count": follower_count,
            "capsule_count": capsule_count,
            "is_following": is_following,
            "is_own": is_own,
        }
        html_parts.append(templates.get_template("partials/sieve_card.html").render(sieve=card_data))

    return HTMLResponse(content="".join(html_parts))


@router.get("/discover/capsules", response_class=HTMLResponse)
async def htmx_discover_capsules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Recent capsules from public sieves
    query = (
        select(Capsule)
        .join(Sieve, Capsule.sieve_id == Sieve.id)
        .where(Sieve.is_public == True)  # noqa: E712
        .order_by(Capsule.created_at.desc())
        .limit(20)
    )
    result = await db.execute(query)
    capsules = result.scalars().all()

    if not capsules:
        return HTMLResponse(
            content='<div class="empty-state"><h3>No trending capsules yet</h3><p>Be the first to share knowledge publicly.</p></div>'
        )

    html_parts = []
    for c in capsules:
        item = await _capsule_to_feed_dict(c, db)
        html_parts.append(templates.get_template("partials/feed_card.html").render(capsule=item))

    return HTMLResponse(content="".join(html_parts))


# ---------------------------------------------------------------------------
# Follow / Unfollow routes
# ---------------------------------------------------------------------------


@router.post("/sieves/@{username}/follow", response_class=HTMLResponse)
async def htmx_follow_sieve(
    username: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get my sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    my_sieve = result.scalar_one_or_none()
    if not my_sieve:
        raise HTTPException(status_code=404, detail="Your sieve not found")

    # Get target sieve
    result = await db.execute(
        select(Sieve).join(User, Sieve.user_id == User.id).where(User.username == username)
    )
    target_sieve = result.scalar_one_or_none()
    if not target_sieve:
        raise HTTPException(status_code=404, detail="Sieve not found")

    if my_sieve.id == target_sieve.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    # Check existing follow
    existing = await db.execute(
        select(Follow).where(
            Follow.follower_sieve_id == my_sieve.id,
            Follow.followed_sieve_id == target_sieve.id,
        )
    )
    if existing.scalar_one_or_none():
        # Already following — return "Following" button
        return HTMLResponse(
            content=f'<button class="follow-btn follow-btn--following" hx-delete="/htmx/sieves/@{username}/follow" hx-swap="outerHTML">Following</button>'
        )

    follow = Follow(follower_sieve_id=my_sieve.id, followed_sieve_id=target_sieve.id)
    db.add(follow)
    await db.commit()

    return HTMLResponse(
        content=f'<button class="follow-btn follow-btn--following" hx-delete="/htmx/sieves/@{username}/follow" hx-swap="outerHTML">Following</button>'
    )


@router.delete("/sieves/@{username}/follow", response_class=HTMLResponse)
async def htmx_unfollow_sieve(
    username: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get my sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    my_sieve = result.scalar_one_or_none()
    if not my_sieve:
        raise HTTPException(status_code=404, detail="Your sieve not found")

    # Get target sieve
    result = await db.execute(
        select(Sieve).join(User, Sieve.user_id == User.id).where(User.username == username)
    )
    target_sieve = result.scalar_one_or_none()
    if not target_sieve:
        raise HTTPException(status_code=404, detail="Sieve not found")

    # Remove follow
    existing = await db.execute(
        select(Follow).where(
            Follow.follower_sieve_id == my_sieve.id,
            Follow.followed_sieve_id == target_sieve.id,
        )
    )
    follow = existing.scalar_one_or_none()
    if follow:
        await db.delete(follow)
        await db.commit()

    return HTMLResponse(
        content=f'<button class="follow-btn follow-btn--follow" hx-post="/htmx/sieves/@{username}/follow" hx-swap="outerHTML">Follow</button>'
    )


# ---------------------------------------------------------------------------
# Settings routes
# ---------------------------------------------------------------------------


@router.put("/sieves/me", response_class=HTMLResponse)
async def htmx_update_my_sieve(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(status_code=404, detail="Sieve not found")

    form = await request.form()

    bio = form.get("bio")
    if bio is not None:
        sieve.bio = bio[:500]

    avatar_url = form.get("avatar_url")
    if avatar_url is not None:
        sieve.avatar_url = avatar_url[:2000] if avatar_url else None

    is_public = form.get("is_public")
    sieve.is_public = is_public in ("true", "True", "on", True)

    await db.commit()

    return HTMLResponse(
        content='<div class="alert alert-success">Settings saved successfully.</div>'
    )
