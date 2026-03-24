from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleListResponse
from sieve.api.sieves.routes import _get_sieve_counts, _sieve_to_profile
from sieve.api.sieves.schemas import SieveProfileResponse
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, User
from sieve.utils import escape_like

router = APIRouter(prefix="/api/discover", tags=["discover"])


class DiscoverSievesResponse(BaseModel):
    sieves: list[SieveProfileResponse]
    total: int


@router.get("/sieves", response_model=DiscoverSievesResponse)
async def discover_sieves(
    search: str | None = Query(None, description="Search by name or display_name"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Browse public sieves with optional search."""
    query = (
        select(Sieve, User)
        .join(User, Sieve.user_id == User.id)
        .where(Sieve.is_public.is_(True))
    )

    if search:
        search_term = f"%{escape_like(search)}%"
        query = query.where(
            or_(
                Sieve.name.ilike(search_term),
                User.display_name.ilike(search_term),
            )
        )

    # Count total matching
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(Sieve.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    sieves = []
    for sieve, user in rows:
        counts = await _get_sieve_counts(db, sieve.id)
        sieves.append(_sieve_to_profile(sieve, user, *counts))

    return DiscoverSievesResponse(sieves=sieves, total=total)


@router.get("/capsules", response_model=CapsuleListResponse)
async def discover_capsules(
    tag: str | None = Query(None, description="Filter by tag"),
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search title/content"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Browse public capsules with optional filters."""
    # Only capsules from public sieves with active status
    query = (
        select(Capsule)
        .join(Sieve, Capsule.sieve_id == Sieve.id)
        .where(Sieve.is_public.is_(True), Capsule.status == "active")
    )

    if tag:
        # Use cast to String + ILIKE for SQLite compatibility
        # (PostgreSQL ARRAY .any() won't work with SQLite test patches)
        query = query.where(Capsule.tags.cast(String).ilike(f"%{escape_like(tag)}%"))

    if category:
        query = query.where(Capsule.category.ilike(f"%{escape_like(category)}%"))

    if search:
        search_term = f"%{escape_like(search)}%"
        query = query.where(
            or_(
                Capsule.title.ilike(search_term),
                Capsule.core_insight.ilike(search_term),
            )
        )

    # Count total matching
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(Capsule.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    capsules = result.scalars().all()

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=total,
    )
