from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.api.capsules.schemas import (
    CapsuleCreate,
    CapsuleListResponse,
    CapsuleResponse,
    CapsuleUpdate,
    SearchRequest,
)
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, User

router = APIRouter(prefix="/api/capsules", tags=["capsules"])


def capsule_to_response(c: Capsule) -> CapsuleResponse:
    """Convert a Capsule ORM model to a CapsuleResponse schema."""
    return CapsuleResponse(
        id=str(c.id),
        title=c.title,
        executive_summary=c.executive_summary,
        core_insight=c.core_insight,
        full_content=c.full_content,
        tags=c.tags or [],
        keywords=c.keywords or [],
        topics=c.topics or [],
        category=c.category or "",
        domain=c.domain or "",
        difficulty=c.difficulty or "beginner",
        content_type=c.content_type or "insight",
        author=c.author or "personal",
        source_url=c.source_url,
        capture_method=c.capture_method or "manual",
        source_type=c.source_type or "",
        status=c.status or "active",
        pinned=c.pinned,
        skill_eligible=c.skill_eligible,
        created_at=c.created_at.isoformat() if c.created_at else "",
    )


async def _get_user_sieve(user: User, db: AsyncSession) -> Sieve:
    """Get the current user's sieve, raising 404 if not found."""
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found for user",
        )
    return sieve


@router.get("/", response_model=CapsuleListResponse)
async def list_capsules(
    search: str | None = Query(None, description="Search term for title/content"),
    category: str | None = Query(None),
    domain: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List capsules for the current user's sieve with optional filters."""
    sieve = await _get_user_sieve(user, db)

    query = select(Capsule).where(Capsule.sieve_id == sieve.id)

    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Capsule.title.ilike(search_term),
                Capsule.executive_summary.ilike(search_term),
                Capsule.core_insight.ilike(search_term),
                Capsule.full_content.ilike(search_term),
            )
        )

    if category:
        query = query.where(Capsule.category.ilike(f"%{category}%"))

    if domain:
        query = query.where(Capsule.domain.ilike(f"%{domain}%"))

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


@router.post("/", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
async def create_capsule(
    body: CapsuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new capsule directly."""
    sieve = await _get_user_sieve(user, db)

    capsule = Capsule(
        sieve_id=sieve.id,
        title=body.title,
        executive_summary=body.executive_summary,
        core_insight=body.core_insight,
        full_content=body.full_content,
        tags=body.tags,
        keywords=body.keywords,
        topics=body.topics,
        category=body.category,
        domain=body.domain,
        difficulty=body.difficulty,
        content_type=body.content_type,
        author=body.author,
        source_url=body.source_url,
        capture_method=body.capture_method,
        source_type=body.source_type,
        pinned=body.pinned,
        skill_eligible=body.skill_eligible,
    )
    db.add(capsule)
    await db.commit()
    await db.refresh(capsule)

    return capsule_to_response(capsule)


@router.get("/{capsule_id}", response_model=CapsuleResponse)
async def get_capsule(
    capsule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single capsule by ID."""
    sieve = await _get_user_sieve(user, db)

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()

    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    return capsule_to_response(capsule)


@router.put("/{capsule_id}", response_model=CapsuleResponse)
async def update_capsule(
    capsule_id: str,
    body: CapsuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing capsule."""
    sieve = await _get_user_sieve(user, db)

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()

    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    # Only update fields that were explicitly set
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(capsule, field, value)

    await db.commit()
    await db.refresh(capsule)

    return capsule_to_response(capsule)


@router.delete("/{capsule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capsule(
    capsule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a capsule."""
    sieve = await _get_user_sieve(user, db)

    result = await db.execute(
        select(Capsule).where(Capsule.id == capsule_id, Capsule.sieve_id == sieve.id)
    )
    capsule = result.scalar_one_or_none()

    if not capsule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Capsule not found",
        )

    await db.delete(capsule)
    await db.commit()


@router.post("/search", response_model=CapsuleListResponse)
async def search_capsules(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search capsules using ILIKE text matching.

    TODO: Replace with pgvector semantic search in a future iteration.
    """
    sieve = await _get_user_sieve(user, db)

    search_term = f"%{body.query}%"
    query = select(Capsule).where(
        Capsule.sieve_id == sieve.id,
        or_(
            Capsule.title.ilike(search_term),
            Capsule.executive_summary.ilike(search_term),
            Capsule.core_insight.ilike(search_term),
            Capsule.full_content.ilike(search_term),
        ),
    )

    if body.category:
        query = query.where(Capsule.category.ilike(f"%{body.category}%"))

    if body.domain:
        query = query.where(Capsule.domain.ilike(f"%{body.domain}%"))

    if body.difficulty:
        query = query.where(Capsule.difficulty == body.difficulty)

    if body.author:
        query = query.where(Capsule.author.ilike(f"%{body.author}%"))

    query = query.order_by(Capsule.created_at.desc()).limit(body.limit)
    result = await db.execute(query)
    capsules = result.scalars().all()

    return CapsuleListResponse(
        capsules=[capsule_to_response(c) for c in capsules],
        total=len(capsules),
    )
