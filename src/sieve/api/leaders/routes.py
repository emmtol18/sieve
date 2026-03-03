from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import require_admin
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleListResponse
from sieve.api.leaders.schemas import (
    LeaderCreate,
    LeaderListResponse,
    LeaderResponse,
    LeaderUpdate,
)
from sieve.db.database import get_db
from sieve.db.models import Capsule, Leader, User
from sieve.utils import escape_like

router = APIRouter(prefix="/api/leaders", tags=["leaders"])


def leader_to_response(leader: Leader) -> LeaderResponse:
    return LeaderResponse(
        id=str(leader.id),
        name=leader.name,
        slug=leader.slug,
        description=leader.description,
        bio=leader.bio or "",
        expertise_domain=leader.expertise_domain or "",
        avatar_url=leader.avatar_url,
        twitter_url=leader.twitter_url,
        linkedin_url=leader.linkedin_url,
        author_url=leader.author_url,
        topics=leader.topics or [],
        is_featured=leader.is_featured,
        capsule_count=leader.capsule_count,
        created_at=leader.created_at.isoformat() if leader.created_at else "",
    )


@router.get("/", response_model=LeaderListResponse)
async def list_leaders(
    domain: str | None = Query(None, description="Filter by expertise domain"),
    search: str | None = Query(None, description="Search by name or description"),
    db: AsyncSession = Depends(get_db),
) -> LeaderListResponse:
    stmt = select(Leader)

    if domain:
        stmt = stmt.where(Leader.expertise_domain == domain)
    if search:
        pattern = f"%{escape_like(search)}%"
        stmt = stmt.where(
            Leader.name.ilike(pattern) | Leader.description.ilike(pattern) | Leader.bio.ilike(pattern)
        )

    stmt = stmt.order_by(Leader.is_featured.desc(), Leader.name.asc()).limit(200)
    result = await db.execute(stmt)
    leaders = result.scalars().all()

    return LeaderListResponse(
        leaders=[leader_to_response(l) for l in leaders],
        total=len(leaders),
    )


@router.get("/{slug}", response_model=LeaderResponse)
async def get_leader(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> LeaderResponse:
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leader not found"
        )
    return leader_to_response(leader)


@router.get("/{slug}/capsules", response_model=CapsuleListResponse)
async def get_leader_capsules(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get capsules for a leader. Public endpoint."""
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")

    query = (
        select(Capsule)
        .where(Capsule.pack_id == leader.id)
        .order_by(Capsule.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    capsules = result.scalars().all()

    count_q = select(func.count()).where(Capsule.pack_id == leader.id)
    total = (await db.execute(count_q)).scalar() or 0

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=total,
    )


@router.post("/", response_model=LeaderResponse, status_code=status.HTTP_201_CREATED)
async def create_leader(
    data: LeaderCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> LeaderResponse:
    # Check slug uniqueness
    existing = await db.execute(select(Leader).where(Leader.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A leader with this slug already exists",
        )

    leader = Leader(**data.model_dump())
    db.add(leader)
    await db.commit()
    await db.refresh(leader)
    return leader_to_response(leader)


@router.put("/{slug}", response_model=LeaderResponse)
async def update_leader(
    slug: str,
    data: LeaderUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> LeaderResponse:
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leader not found"
        )

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(leader, key, value)

    await db.commit()
    await db.refresh(leader)
    return leader_to_response(leader)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leader(
    slug: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Leader).where(Leader.slug == slug))
    leader = result.scalar_one_or_none()
    if not leader:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leader not found"
        )

    await db.delete(leader)
    await db.commit()
