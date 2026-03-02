from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user, verify_token
from sieve.api.capsules.routes import capsule_to_response
from sieve.db.database import get_db
from sieve.db.models import Capsule, Follow, Sieve, Skill, SkillCapsule, User
from sieve.utils import extract_domain

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")

LOGIN_REDIRECT = RedirectResponse(url="/login", status_code=303)


def _is_authenticated(request: Request) -> bool:
    """Check if the request has a valid sieve_token cookie."""
    token = request.cookies.get("sieve_token")
    if not token:
        return False
    try:
        verify_token(token)
        return True
    except HTTPException:
        return False


def _render(request: Request, template: str, context: dict | None = None) -> HTMLResponse:
    """Render a template after verifying authentication, or redirect to login."""
    ctx = {"request": request, **(context or {})}
    return templates.TemplateResponse(template, ctx)


def _protected(request: Request, template: str, context: dict | None = None) -> HTMLResponse:
    """Render a template if authenticated, otherwise redirect to login."""
    if not _is_authenticated(request):
        return LOGIN_REDIRECT
    return _render(request, template, context)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return _protected(request, "feed.html")


@router.get("/sieve", response_class=HTMLResponse)
async def sieve_page(request: Request, db: AsyncSession = Depends(get_db)):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    categories = []
    domains = []
    try:
        user_id = verify_token(request.cookies.get("sieve_token"))
        result = await db.execute(select(Sieve).where(Sieve.user_id == user_id))
        sieve = result.scalar_one_or_none()

        if sieve:
            cat_result = await db.execute(
                select(Capsule.category)
                .where(Capsule.sieve_id == sieve.id, Capsule.category.isnot(None))
                .distinct()
            )
            categories = sorted([row[0] for row in cat_result.all() if row[0]])

            dom_result = await db.execute(
                select(Capsule.domain)
                .where(Capsule.sieve_id == sieve.id, Capsule.domain.isnot(None))
                .distinct()
            )
            domains = sorted([row[0] for row in dom_result.all() if row[0]])
    except Exception:
        pass

    return _render(request, "sieve.html", {"capsules": [], "categories": categories, "domains": domains})


@router.get("/discover", response_class=HTMLResponse)
async def discover_page(request: Request):
    return _protected(request, "discover.html")


@router.get("/compile", response_class=HTMLResponse)
async def compile_page(request: Request, db: AsyncSession = Depends(get_db)):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    from pathlib import Path

    from sieve.config import settings

    user_id = verify_token(request.cookies.get("sieve_token"))
    result = await db.execute(select(User.email).where(User.id == user_id))
    user_email = result.scalar_one_or_none() or ""

    return _render(
        request,
        "compile.html",
        {
            "user_email": user_email,
            "database_url": settings.database_url,
            "project_dir": str(Path.cwd()),
        },
    )


@router.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request):
    return _protected(request, "skills.html")


@router.get("/skills/{skill_id}", response_class=HTMLResponse)
async def skill_detail(
    request: Request, skill_id: str, db: AsyncSession = Depends(get_db)
):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    user_id = verify_token(request.cookies.get("sieve_token"))
    result = await db.execute(select(Sieve).where(Sieve.user_id == user_id))
    sieve = result.scalar_one_or_none()

    skill = None
    source_capsules = []
    if sieve:
        result = await db.execute(
            select(Skill).where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
        )
        row = result.scalar_one_or_none()
        if row:
            from sieve.api.skills.routes import skill_to_response
            skill = skill_to_response(row).model_dump()

            # Load source capsules
            result = await db.execute(
                select(SkillCapsule).where(SkillCapsule.skill_id == row.id)
            )
            links = result.scalars().all()
            for link in links:
                cap_result = await db.execute(
                    select(Capsule).where(Capsule.id == link.capsule_id)
                )
                cap = cap_result.scalar_one_or_none()
                if cap:
                    source_capsules.append({
                        "id": str(cap.id),
                        "title": cap.title,
                        "role": link.role,
                    })

    return _render(
        request, "skill_detail.html",
        {"skill": skill, "skill_id": skill_id, "source_capsules": source_capsules},
    )


@router.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    return _protected(request, "import.html")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _render(request, "login.html")


@router.get("/capsule/{capsule_id}", response_class=HTMLResponse)
async def capsule_detail(
    request: Request, capsule_id: str, db: AsyncSession = Depends(get_db)
):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    user_id = verify_token(request.cookies.get("sieve_token"))
    result = await db.execute(select(Sieve).where(Sieve.user_id == user_id))
    sieve = result.scalar_one_or_none()

    capsule = None
    if sieve:
        result = await db.execute(
            select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
        )
        row = result.scalar_one_or_none()
        if row:
            capsule = capsule_to_response(row).model_dump()

    return _render(
        request, "capsule_detail.html", {"capsule": capsule, "capsule_id": capsule_id}
    )


@router.get("/sieve/@{username}", response_class=HTMLResponse)
async def sieve_profile(request: Request, username: str, db: AsyncSession = Depends(get_db)):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    # Get the viewed user's sieve
    result = await db.execute(
        select(User, Sieve).join(Sieve, User.id == Sieve.user_id).where(User.username == username)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    target_user, target_sieve = row

    # Get current user info for follow status
    current_user = None
    my_sieve = None
    try:
        current_user = await get_current_user(request, db)
        sieve_result = await db.execute(select(Sieve).where(Sieve.user_id == current_user.id))
        my_sieve = sieve_result.scalar_one_or_none()
    except HTTPException:
        pass

    # Counts
    follower_count = (
        await db.execute(select(func.count()).where(Follow.followed_sieve_id == target_sieve.id))
    ).scalar() or 0

    following_count = (
        await db.execute(select(func.count()).where(Follow.follower_sieve_id == target_sieve.id))
    ).scalar() or 0

    capsule_count = (
        await db.execute(select(func.count()).where(Capsule.sieve_id == target_sieve.id, Capsule.status == "active"))
    ).scalar() or 0

    # Follow status
    is_following = False
    is_own = my_sieve is not None and my_sieve.id == target_sieve.id
    if my_sieve and not is_own:
        follow_check = await db.execute(
            select(Follow).where(
                Follow.follower_sieve_id == my_sieve.id,
                Follow.followed_sieve_id == target_sieve.id,
            )
        )
        is_following = follow_check.scalar_one_or_none() is not None

    # Get capsules: all if own profile, else only if sieve is public
    capsules = []
    if is_own or target_sieve.is_public:
        capsule_result = await db.execute(
            select(Capsule)
            .where(Capsule.sieve_id == target_sieve.id)
            .order_by(Capsule.created_at.desc())
            .limit(50)
        )
        capsule_objs = capsule_result.scalars().all()
        for c in capsule_objs:
            capsules.append(
                {
                    "id": str(c.id),
                    "title": c.title,
                    "executive_summary": c.executive_summary,
                    "core_insight": c.core_insight,
                    "tags": c.tags or [],
                    "source_url": c.source_url,
                    "source_domain": extract_domain(c.source_url),
                    "created_at": c.created_at.strftime("%Y-%m-%d") if c.created_at else "",
                    "author_username": target_user.username,
                }
            )

    profile = {
        "display_name": target_user.display_name,
        "username": target_user.username,
        "bio": target_sieve.bio or "",
        "capsule_count": capsule_count,
        "follower_count": follower_count,
        "following_count": following_count,
        "is_following": is_following,
        "is_own": is_own,
    }

    return _render(request, "profile.html", {"profile": profile, "capsules": capsules})


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    if not _is_authenticated(request):
        return LOGIN_REDIRECT

    try:
        current_user = await get_current_user(request, db)
    except HTTPException:
        return LOGIN_REDIRECT

    sieve_result = await db.execute(select(Sieve).where(Sieve.user_id == current_user.id))
    sieve = sieve_result.scalar_one_or_none()

    return _render(
        request,
        "settings.html",
        {
            "user": current_user,
            "sieve": sieve,
        },
    )
