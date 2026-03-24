from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.db.database import get_db
from sieve.db.models import Capsule, Follow, Sieve, User

from .schemas import SieveProfileResponse, SieveUpdateRequest

router = APIRouter(prefix="/api/sieves", tags=["sieves"])


def _sieve_to_profile(
    sieve: Sieve,
    user: User,
    capsule_count: int,
    follower_count: int,
    following_count: int,
) -> SieveProfileResponse:
    return SieveProfileResponse(
        id=str(sieve.id),
        name=sieve.name,
        username=user.username,
        display_name=user.display_name,
        bio=sieve.bio or "",
        avatar_url=sieve.avatar_url,
        is_public=sieve.is_public,
        capsule_count=capsule_count,
        follower_count=follower_count,
        following_count=following_count,
        created_at=sieve.created_at.isoformat() if sieve.created_at else "",
    )


async def _get_sieve_counts(db: AsyncSession, sieve_id) -> tuple[int, int, int]:
    """Return (capsule_count, follower_count, following_count) for a sieve."""
    capsule_q = select(func.count()).select_from(Capsule).where(
        Capsule.sieve_id == sieve_id, Capsule.status == "active"
    )
    follower_q = select(func.count()).select_from(Follow).where(
        Follow.followed_sieve_id == sieve_id
    )
    following_q = select(func.count()).select_from(Follow).where(
        Follow.follower_sieve_id == sieve_id
    )

    capsule_result = await db.execute(capsule_q)
    follower_result = await db.execute(follower_q)
    following_result = await db.execute(following_q)

    return (
        capsule_result.scalar() or 0,
        follower_result.scalar() or 0,
        following_result.scalar() or 0,
    )


# ---- /me routes (must be before /@{username} to avoid path conflicts) ----


@router.get("/me", response_model=SieveProfileResponse)
async def get_own_sieve(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's own sieve profile."""
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found for user",
        )

    counts = await _get_sieve_counts(db, sieve.id)
    return _sieve_to_profile(sieve, user, *counts)


@router.put("/me", response_model=SieveProfileResponse)
async def update_own_sieve(
    body: SieveUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's sieve fields (partial update)."""
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found for user",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sieve, field, value)

    await db.commit()
    await db.refresh(sieve)

    counts = await _get_sieve_counts(db, sieve.id)
    return _sieve_to_profile(sieve, user, *counts)


# ---- /@{username} routes ----


@router.get("/@{username}", response_model=SieveProfileResponse)
async def get_sieve_by_username(
    username: str,
    db: AsyncSession = Depends(get_db),
):
    """Return a public sieve by username. Returns 404 if private or not found."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found",
        )

    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve or not sieve.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found",
        )

    counts = await _get_sieve_counts(db, sieve.id)
    return _sieve_to_profile(sieve, user, *counts)


# ---- Follow / Unfollow ----


@router.post("/@{username}/follow", status_code=status.HTTP_201_CREATED)
async def follow_sieve(
    username: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Follow a public sieve by username."""
    # Look up target user
    result = await db.execute(select(User).where(User.username == username))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found",
        )

    # Look up target sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == target_user.id))
    target_sieve = result.scalar_one_or_none()
    if not target_sieve or not target_sieve.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found",
        )

    # Look up follower's sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    my_sieve = result.scalar_one_or_none()
    if not my_sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your sieve not found",
        )

    # Cannot follow yourself
    if my_sieve.id == target_sieve.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot follow yourself",
        )

    # Check if already following
    result = await db.execute(
        select(Follow).where(
            Follow.follower_sieve_id == my_sieve.id,
            Follow.followed_sieve_id == target_sieve.id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already following this sieve",
        )

    follow = Follow(
        follower_sieve_id=my_sieve.id,
        followed_sieve_id=target_sieve.id,
    )
    db.add(follow)
    await db.commit()

    return {"detail": "Followed"}


@router.delete("/@{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
async def unfollow_sieve(
    username: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unfollow a sieve by username."""
    # Look up target user
    result = await db.execute(select(User).where(User.username == username))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this sieve",
        )

    # Look up target sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == target_user.id))
    target_sieve = result.scalar_one_or_none()
    if not target_sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this sieve",
        )

    # Look up follower's sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    my_sieve = result.scalar_one_or_none()
    if not my_sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Your sieve not found",
        )

    # Find the follow relationship
    result = await db.execute(
        select(Follow).where(
            Follow.follower_sieve_id == my_sieve.id,
            Follow.followed_sieve_id == target_sieve.id,
        )
    )
    follow = result.scalar_one_or_none()
    if not follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this sieve",
        )

    await db.delete(follow)
    await db.commit()
