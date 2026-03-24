from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleListResponse
from sieve.db.database import get_db
from sieve.db.models import Capsule, Follow, Sieve, User

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("/", response_model=CapsuleListResponse)
async def get_feed(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's feed (own + followed sieves), reverse-chronological."""
    # Get user's sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        return CapsuleListResponse(capsules=[], total=0)

    # Get IDs of sieves the user follows
    followed_q = select(Follow.followed_sieve_id).where(
        Follow.follower_sieve_id == sieve.id
    )
    followed_result = await db.execute(followed_q)
    followed_ids = [row[0] for row in followed_result.all()]

    # Combine own sieve + followed sieves
    all_sieve_ids = [sieve.id] + followed_ids

    # Query capsules from those sieves
    query = select(Capsule).where(
        Capsule.sieve_id.in_(all_sieve_ids),
        Capsule.status == "active",
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
