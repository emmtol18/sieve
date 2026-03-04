from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user, require_admin
from sieve.api.capsules.routes import capsule_to_response
from sieve.api.capsules.schemas import (
    BatchCaptureRequest,
    BatchCaptureResponse,
    BatchCaptureResultItem,
    CapsuleResponse,
    CaptureRequest,
)
from sieve.api.capture.pipeline import CapturePipeline
from sieve.db.database import get_db
from sieve.db.models import Capsule, Creator, Sieve, User

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
    # Run the capture pipeline
    pipeline = CapturePipeline()
    try:
        capsule_data = await pipeline.process(body)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Either/or: creator pack capsules don't belong to a personal sieve
    creator = None
    if body.creator_id:
        result = await db.execute(select(Creator).where(Creator.id == body.creator_id))
        creator = result.scalar_one_or_none()
        if not creator:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found"
            )
        sieve_id = None
        pack_id = creator.id
    else:
        result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
        sieve = result.scalar_one_or_none()
        if not sieve:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sieve not found for user",
            )
        sieve_id = sieve.id
        pack_id = None

    # Create the capsule
    capsule = Capsule(
        sieve_id=sieve_id,
        pack_id=pack_id,
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

    # Update creator's capsule_count after commit
    if body.creator_id and creator:
        count_result = await db.execute(
            select(func.count()).where(Capsule.pack_id == body.creator_id)
        )
        creator.capsule_count = count_result.scalar() or 0
        await db.commit()

    return capsule_to_response(capsule)


@router.post("/batch", response_model=BatchCaptureResponse)
async def batch_capture(
    body: BatchCaptureRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Batch capture multiple content items as capsules for a creator pack.

    Admin-only. Processes all items in parallel via the LLM pipeline.
    """
    # Verify creator exists
    result = await db.execute(select(Creator).where(Creator.id == body.creator_id))
    creator = result.scalar_one_or_none()
    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Creator not found"
        )

    async def process_one(item):
        pipeline = CapturePipeline()
        try:
            req = CaptureRequest(content=item.content, source_url=item.source_url)
            capsule_data = await pipeline.process(req)

            capsule = Capsule(
                sieve_id=None,
                pack_id=creator.id,
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
                source_url=item.source_url,
                capture_method="batch",
                source_type=body.source_type,
            )
            db.add(capsule)
            await db.flush()
            return BatchCaptureResultItem(
                status="success",
                capsule_id=str(capsule.id),
                title=capsule.title,
            )
        except Exception as e:
            return BatchCaptureResultItem(
                status="error",
                error=str(e),
            )

    results = [await process_one(item) for item in body.items]
    await db.commit()

    # Update creator capsule count
    count_result = await db.execute(
        select(func.count()).where(Capsule.pack_id == creator.id)
    )
    creator.capsule_count = count_result.scalar() or 0
    await db.commit()

    succeeded = sum(1 for r in results if r.status == "success")
    return BatchCaptureResponse(
        results=list(results),
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
    )
