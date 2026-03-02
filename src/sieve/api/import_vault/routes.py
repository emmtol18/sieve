import logging
import zipfile

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import get_current_user
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, User
from sieve.import_vault.parser import parse_obsidian_note
from sieve.llm.client import LLMClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["import"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


@router.post("/vault")
async def import_vault(
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Import an Obsidian vault from a .zip file.

    Processes markdown files, runs LLM extraction, deduplicates,
    and creates capsules.
    """
    # Validate file type
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .zip archive",
        )

    # Read and validate file size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File exceeds maximum size of 100MB",
        )

    # Validate zip
    import io

    try:
        zf = zipfile.ZipFile(io.BytesIO(contents))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid zip file",
        )

    # Get user's sieve
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sieve not found for user",
        )

    # Get existing capsule titles for dedup
    existing_result = await db.execute(
        select(Capsule.title).where(Capsule.sieve_id == sieve.id)
    )
    existing_titles = {row[0].lower() for row in existing_result.all()}

    llm = LLMClient()
    imported = 0
    skipped = 0
    duplicates = 0

    for name in zf.namelist():
        # Skip macOS metadata and non-markdown files
        if "__MACOSX" in name:
            continue
        if not name.endswith(".md"):
            continue

        raw = zf.read(name).decode("utf-8", errors="replace")
        filename = name.split("/")[-1]  # Use just the filename, not full path

        parsed = parse_obsidian_note(raw, filename)
        if parsed is None:
            skipped += 1
            continue

        # Run LLM extraction
        try:
            capsule_data = await llm.extract_capsule(parsed["full_content"])
        except Exception:
            logger.exception("LLM extraction failed for %s", name)
            skipped += 1
            continue

        # Use parsed title if available
        title = parsed["title"] or capsule_data.get("title", "Untitled")

        # Dedup by title
        if title.lower() in existing_titles:
            duplicates += 1
            continue

        # For notes with good frontmatter, prefer parsed tags over LLM tags
        tags = capsule_data.get("tags", [])
        if parsed["has_metadata"] and parsed["tags"]:
            tags = parsed["tags"]

        capsule = Capsule(
            sieve_id=sieve.id,
            title=title,
            executive_summary=capsule_data.get("executive_summary", ""),
            core_insight=capsule_data.get("core_insight", ""),
            full_content=capsule_data.get("full_content", ""),
            tags=tags,
            keywords=capsule_data.get("keywords", []),
            topics=capsule_data.get("topics", []),
            category=capsule_data.get("category", ""),
            domain=capsule_data.get("domain", ""),
            difficulty=capsule_data.get("difficulty", "beginner"),
            content_type=capsule_data.get("content_type", "insight"),
            author=capsule_data.get("author", "personal"),
            capture_method="obsidian",
            source_type=capsule_data.get("source_type", ""),
        )
        db.add(capsule)
        existing_titles.add(title.lower())
        imported += 1

    await db.commit()

    return {"imported": imported, "skipped": skipped, "duplicates": duplicates}
