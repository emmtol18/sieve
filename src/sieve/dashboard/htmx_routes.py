import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import create_access_token, get_current_user, hash_password, verify_password
from sieve.api.auth.routes import COOKIE_NAME, set_auth_cookie
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CaptureRequest
from sieve.api.capture.pipeline import CapturePipeline
from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Capsule, Follow, Leader, Sieve, User
from sieve.utils import escape_like, extract_domain

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
        term = f"%{escape_like(search)}%"
        query = query.where(
            or_(
                Capsule.title.ilike(term),
                Capsule.executive_summary.ilike(term),
                Capsule.core_insight.ilike(term),
                Capsule.full_content.ilike(term),
            )
        )
    if category:
        query = query.where(Capsule.category.ilike(f"%{escape_like(category)}%"))
    if domain:
        query = query.where(Capsule.domain.ilike(f"%{escape_like(domain)}%"))

    query = query.order_by(Capsule.created_at.desc()).limit(50)
    result = await db.execute(query)
    capsules = result.scalars().all()

    capsule_dicts = [capsule_to_response(c).model_dump() for c in capsules]

    is_filtered = bool(search or category or domain)

    grouped_capsules: dict[str, list] | None = None
    if not is_filtered:
        grouped_capsules = {}
        for c in capsule_dicts:
            cat = c.get("category") or "Uncategorized"
            grouped_capsules.setdefault(cat, []).append(c)

    return _render_partial(
        "partials/capsule_grid.html",
        capsules=capsule_dicts,
        grouped_capsules=grouped_capsules,
        count=len(capsule_dicts),
        search_term=search or "",
    )


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


@router.post("/compile/", response_class=HTMLResponse)
async def htmx_compile(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from pathlib import Path

    from sieve.compiler.compiler import SkillCompiler

    form = await request.form()
    by = form.get("by", "capsule")
    if by not in ("capsule", "category", "author", "pack"):
        return _render_partial("partials/compile_result.html", error=f"Invalid grouping: {by}")

    if not settings.fuel_api_key:
        return _render_partial("partials/compile_result.html", error="SIEVE_FUEL_API_KEY is not set.")

    # Fetch capsules from DB directly
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        return _render_partial("partials/compile_result.html", error="No sieve found for user.")

    capsule_result = await db.execute(
        select(Capsule).where(Capsule.sieve_id == sieve.id)
    )
    capsule_rows = capsule_result.scalars().all()
    capsules = [
        {
            "id": str(c.id),
            "title": c.title,
            "executive_summary": c.executive_summary,
            "core_insight": c.core_insight,
            "full_content": c.full_content,
            "tags": c.tags or [],
            "category": c.category or "",
            "domain": c.domain or "",
            "author": c.author or "personal",
            "pack_id": str(c.pack_id) if c.pack_id else None,
            "skill_eligible": c.skill_eligible,
        }
        for c in capsule_rows
    ]

    output_dir = Path(".claude/skills")
    compiler = SkillCompiler()

    try:
        paths = await compiler.compile_to_skills(
            output_dir=output_dir, by=by, all_capsules=True, capsules=capsules
        )
    except Exception as e:
        return _render_partial("partials/compile_result.html", error=str(e))

    path_strs = [str(p) for p in paths]
    return _render_partial(
        "partials/compile_result.html",
        paths=path_strs,
        count=len(paths),
        output_dir=str(output_dir),
    )


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
        "source_domain": extract_domain(capsule.source_url),
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
        query = select(Capsule).where(Capsule.sieve_id == sieve.id, Capsule.status == "active")
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
        query = select(Capsule).where(Capsule.sieve_id.in_(followed_ids), Capsule.status == "active")
    else:  # "all" — own + followed
        follow_result = await db.execute(
            select(Follow.followed_sieve_id).where(Follow.follower_sieve_id == sieve.id)
        )
        followed_ids = [row[0] for row in follow_result.all()]
        all_sieve_ids = [sieve.id] + followed_ids
        query = select(Capsule).where(Capsule.sieve_id.in_(all_sieve_ids), Capsule.status == "active")

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
        term = f"%{escape_like(search)}%"
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
        .where(Sieve.is_public == True, Capsule.status == "active")  # noqa: E712
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
# Leader routes
# ---------------------------------------------------------------------------


@router.get("/leaders/", response_class=HTMLResponse)
async def htmx_list_leaders(
    domain: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: leader card grid with optional domain filter."""
    query = select(Leader)

    if domain:
        query = query.where(Leader.expertise_domain == domain)
    if search:
        term = f"%{escape_like(search)}%"
        query = query.where(
            or_(Leader.name.ilike(term), Leader.description.ilike(term), Leader.bio.ilike(term))
        )

    query = query.order_by(Leader.is_featured.desc(), Leader.name.asc()).limit(200)
    result = await db.execute(query)
    leaders = result.scalars().all()

    leader_dicts = []
    for l in leaders:
        leader_dicts.append({
            "id": str(l.id),
            "name": l.name,
            "slug": l.slug,
            "description": l.description,
            "bio": l.bio or "",
            "expertise_domain": l.expertise_domain or "",
            "avatar_url": l.avatar_url,
            "capsule_count": l.capsule_count,
            "is_featured": l.is_featured,
        })

    return _render_partial("partials/leader_grid.html", leaders=leader_dicts)


@router.get("/leaders/{slug}/capsules/", response_class=HTMLResponse)
async def htmx_leader_capsules(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """HTMX partial: capsule grid for a specific leader."""
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        return HTMLResponse(content='<div class="empty-state"><h3>Leader not found</h3></div>')

    query = (
        select(Capsule)
        .where(Capsule.pack_id == leader.id)
        .order_by(Capsule.created_at.desc())
        .limit(50)
    )
    result = await db.execute(query)
    capsules = result.scalars().all()
    capsule_dicts = [capsule_to_response(c).model_dump() for c in capsules]

    return _render_partial("partials/capsule_grid.html", capsules=capsule_dicts, grouped_capsules=None, count=len(capsule_dicts))


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
    if not target_sieve or not target_sieve.is_public:
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


# ---------------------------------------------------------------------------
# Import routes
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Skill routes
# ---------------------------------------------------------------------------


@router.get("/skills/", response_class=HTMLResponse)
async def htmx_list_skills(
    request: Request,
    search: str | None = Query(None),
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy.orm import selectinload

    from sieve.db.models import Skill

    query = select(Skill).where(Skill.sieve_id == sieve.id).options(selectinload(Skill.capsule_links))

    if search:
        term = f"%{escape_like(search)}%"
        query = query.where(
            or_(
                Skill.title.ilike(term),
                Skill.description.ilike(term),
                Skill.name.ilike(term),
            )
        )

    query = query.order_by(Skill.created_at.desc()).limit(50)
    result = await db.execute(query)
    skills = result.scalars().all()

    from sieve.api.skills.routes import skill_to_response

    skill_dicts = [skill_to_response(s).model_dump() for s in skills]

    return _render_partial(
        "partials/skill_grid.html",
        skills=skill_dicts,
        count=len(skill_dicts),
        search_term=search or "",
    )


@router.post("/skills/compile", response_class=HTMLResponse)
async def htmx_compile_skill(
    request: Request,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.compiler.compiler import SkillCompiler
    from sieve.db.models import Skill, SkillCapsule

    form = await request.form()
    primary_capsule_id = form.get("primary_capsule_id")
    context_capsule_ids = form.getlist("context_capsule_ids")

    if not primary_capsule_id:
        return _render_partial(
            "partials/compile_result.html", error="Primary capsule is required."
        )

    if not settings.fuel_api_key:
        return _render_partial(
            "partials/compile_result.html", error="SIEVE_FUEL_API_KEY is not set."
        )

    # Load primary capsule
    primary = await _get_capsule_or_404(primary_capsule_id, sieve, db)
    primary_dict = {
        "title": primary.title,
        "executive_summary": primary.executive_summary,
        "core_insight": primary.core_insight,
        "full_content": primary.full_content,
        "tags": primary.tags or [],
    }

    # Load context capsules
    context_dicts = []
    context_capsules = []
    for cid in context_capsule_ids:
        if cid and cid != primary_capsule_id:
            c = await _get_capsule_or_404(cid, sieve, db)
            context_capsules.append(c)
            context_dicts.append({
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
            })

    compiler = SkillCompiler()
    try:
        skill_data = await compiler.compile_capsules(
            primary=primary_dict,
            context_capsules=context_dicts if context_dicts else None,
        )
    except Exception as e:
        return _render_partial("partials/compile_result.html", error=str(e))

    # Save skill to DB
    skill = Skill(
        sieve_id=sieve.id,
        name=skill_data["name"],
        title=skill_data["title"],
        description=skill_data["description"],
        body=skill_data["body"],
    )
    db.add(skill)
    await db.flush()

    # Save capsule associations
    db.add(SkillCapsule(skill_id=skill.id, capsule_id=primary.id, role="primary"))
    for c in context_capsules:
        db.add(SkillCapsule(skill_id=skill.id, capsule_id=c.id, role="context"))

    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/skills/{skill.id}"
    return response


@router.put("/skills/{skill_id}", response_class=HTMLResponse)
async def htmx_update_skill(
    request: Request,
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.db.models import Skill

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    form = await request.form()
    for field in ["title", "description", "body"]:
        value = form.get(field)
        if value is not None:
            setattr(skill, field, value)

    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/skills/{skill_id}"
    return response


@router.delete("/skills/{skill_id}", response_class=HTMLResponse)
async def htmx_delete_skill(
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.db.models import Skill

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    await db.delete(skill)
    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = "/skills"
    return response


@router.post("/skills/{skill_id}/export", response_class=HTMLResponse)
async def htmx_export_skill(
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from pathlib import Path

    from sieve.compiler.templates import SKILL_TEMPLATE
    from sieve.db.models import Skill

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    output_dir = Path(".claude/skills")
    output_dir.mkdir(parents=True, exist_ok=True)

    skill_content = SKILL_TEMPLATE.format(
        name=skill.name, description=skill.description, body=skill.body
    )
    path = output_dir / f"{skill.name}.md"
    path.write_text(skill_content)

    return HTMLResponse(
        content=f'<div class="alert alert-success">Exported to <code>{path}</code></div>'
    )


@router.post("/skills/{skill_id}/recompile", response_class=HTMLResponse)
async def htmx_recompile_skill(
    skill_id: str,
    sieve: Sieve = Depends(get_user_sieve),
    db: AsyncSession = Depends(get_db),
):
    from sieve.compiler.compiler import SkillCompiler
    from sieve.db.models import Skill, SkillCapsule

    result = await db.execute(
        select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    if not settings.fuel_api_key:
        return HTMLResponse(
            content='<div class="alert alert-error">SIEVE_FUEL_API_KEY is not set.</div>'
        )

    # Load linked capsules
    link_result = await db.execute(
        select(SkillCapsule).where(SkillCapsule.skill_id == skill.id)
    )
    links = link_result.scalars().all()

    if not links:
        return HTMLResponse(
            content='<div class="alert alert-error">No linked capsules found for recompilation.</div>'
        )

    primary = None
    context_dicts = []
    for link in links:
        capsule_result = await db.execute(
            select(Capsule).where(Capsule.id == link.capsule_id)
        )
        capsule = capsule_result.scalar_one_or_none()
        if not capsule:
            continue
        capsule_dict = {
            "title": capsule.title,
            "executive_summary": capsule.executive_summary,
            "core_insight": capsule.core_insight,
            "full_content": capsule.full_content,
            "tags": capsule.tags or [],
        }
        if link.role == "primary" and primary is None:
            primary = capsule_dict
        else:
            context_dicts.append(capsule_dict)

    if not primary:
        return HTMLResponse(
            content='<div class="alert alert-error">Primary capsule not found.</div>'
        )

    compiler = SkillCompiler()
    try:
        skill_data = await compiler.compile_capsules(
            primary=primary,
            context_capsules=context_dicts if context_dicts else None,
        )
    except Exception as e:
        return HTMLResponse(
            content=f'<div class="alert alert-error">{e}</div>'
        )

    skill.body = skill_data["body"]
    skill.description = skill_data["description"]
    await db.commit()

    response = HTMLResponse(content="")
    response.headers["HX-Redirect"] = f"/skills/{skill_id}"
    return response


# ---------------------------------------------------------------------------
# Import routes
# ---------------------------------------------------------------------------


@router.post("/import/vault", response_class=HTMLResponse)
async def htmx_import_vault(
    request: Request,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """HTMX wrapper around the vault import endpoint — returns HTML."""
    from sieve.api.import_vault.routes import import_vault

    try:
        result = await import_vault(file=file, user=user, db=db)
    except HTTPException as exc:
        return HTMLResponse(
            content=f'<div class="alert alert-error">{exc.detail}</div>',
            status_code=exc.status_code,
        )

    imported = result["imported"]
    skipped = result["skipped"]
    duplicates = result["duplicates"]

    parts = [f"<strong>{imported}</strong> capsule{'s' if imported != 1 else ''} imported"]
    if skipped:
        parts.append(f"{skipped} skipped")
    if duplicates:
        parts.append(f"{duplicates} duplicate{'s' if duplicates != 1 else ''}")

    summary = ", ".join(parts) + "."

    return HTMLResponse(
        content=f'<div class="alert alert-success">{summary}</div>'
    )
