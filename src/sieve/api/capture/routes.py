from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import CapsuleResponse, CaptureRequest
from sieve.api.capture.pipeline import CapturePipeline
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, User

router = APIRouter(prefix="/api/capture", tags=["capture"])


@router.post("/", response_model=CapsuleResponse, status_code=status.HTTP_201_CREATED)
async def capture(
    body: CaptureRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Capture content (text or URL) and create a capsule via the LLM pipeline.

    Accepts text content or a URL. The pipeline will:
    1. Fetch and extract text from URL if provided
    2. Send content to the LLM for structured extraction
    3. Create a new capsule in the user's sieve
    """
    # Get user's sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found for user",
        )

    # Run the capture pipeline
    pipeline = CapturePipeline()
    try:
        capsule_data = await pipeline.process(body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Create the capsule
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

    return capsule_to_response(capsule)
