from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import require_admin
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleListResponse
from sieve.api.creators.schemas import (
    CreatorCreate,
    CreatorListResponse,
    CreatorResponse,
    CreatorUpdate,
)
from sieve.db.database import get_db
from sieve.db.models import Capsule, Creator, User
from sieve.utils import escape_like

router = APIRouter(prefix="/api/creators", tags=["creators"])


def creator_to_response(creator: Creator) -> CreatorResponse:
    return CreatorResponse(
        id=str(creator.id),
        name=creator.name,
        slug=creator.slug,
        description=creator.description,
        bio=creator.bio or "",
        expertise_domain=creator.expertise_domain or "",
        avatar_url=creator.avatar_url,
        twitter_url=creator.twitter_url,
        linkedin_url=creator.linkedin_url,
        author_url=creator.author_url,
        topics=creator.topics or [],
        is_featured=creator.is_featured,
        capsule_count=creator.capsule_count,
        created_at=creator.created_at.isoformat() if creator.created_at else "",
    )


@router.get("/", response_model=CreatorListResponse)
async def list_creators(
    domain: str | None = Query(None, description="Filter by expertise domain"),
    search: str | None = Query(None, description="Search by name or description"),
    db: AsyncSession = Depends(get_db),
) -> CreatorListResponse:
    stmt = select(Creator)

    if domain:
        stmt = stmt.where(Creator.expertise_domain == domain)
    if search:
        pattern = f"%{escape_like(search)}%"
        stmt = stmt.where(
            Creator.name.ilike(pattern) | Creator.description.ilike(pattern) | Creator.bio.ilike(pattern)
        )

    stmt = stmt.order_by(Creator.is_featured.desc(), Creator.name.asc()).limit(200)
    result = await db.execute(stmt)
    creators = result.scalars().all()

    return CreatorListResponse(
        creators=[creator_to_response(c) for c in creators],
        total=len(creators),
    )


@router.get("/{slug}", response_model=CreatorResponse)
async def get_creator(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> CreatorResponse:
    result = await db.execute(select(Creator).where(Creator.slug == slug))
    creator = result.scalar_one_or_none()
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found"
        )
    return creator_to_response(creator)


@router.get("/{slug}/capsules", response_model=CapsuleListResponse)
async def get_creator_capsules(
    slug: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get capsules for a creator. Public endpoint."""
    result = await db.execute(select(Creator).where(Creator.slug == slug))
    creator = result.scalar_one_or_none()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    query = (
        select(Capsule)
        .where(Capsule.pack_id == creator.id)
        .order_by(Capsule.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    capsules = result.scalars().all()

    count_q = select(func.count()).where(Capsule.pack_id == creator.id)
    total = (await db.execute(count_q)).scalar() or 0

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=total,
    )


@router.post("/", response_model=CreatorResponse, status_code=status.HTTP_201_CREATED)
async def create_creator(
    data: CreatorCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CreatorResponse:
    # Check slug uniqueness
    existing = await db.execute(select(Creator).where(Creator.slug == data.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A creator with this slug already exists",
        )

    creator = Creator(**data.model_dump())
    db.add(creator)
    await db.commit()
    await db.refresh(creator)
    return creator_to_response(creator)


@router.put("/{slug}", response_model=CreatorResponse)
async def update_creator(
    slug: str,
    data: CreatorUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CreatorResponse:
    result = await db.execute(select(Creator).where(Creator.slug == slug))
    creator = result.scalar_one_or_none()
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found"
        )

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(creator, key, value)

    await db.commit()
    await db.refresh(creator)
    return creator_to_response(creator)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creator(
    slug: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Creator).where(Creator.slug == slug))
    creator = result.scalar_one_or_none()
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found"
        )

    await db.delete(creator)
    await db.commit()
