"""Dashboard routes (API + HTMX)."""

import asyncio
import logging
from collections import defaultdict
from typing import Optional

import frontmatter
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..capsule import CapsuleWriter, find_capsule_file, load_capsules
from ..config import Settings
from ..engine import Indexer, Processor

logger = logging.getLogger(__name__)


class CaptureRequest(BaseModel):
    """Request from browser extension."""

    content: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    tags: list[str] = []
    image_data: Optional[str] = None


def create_router(settings: Settings, templates: Jinja2Templates) -> APIRouter:
    """Create the dashboard router."""
    router = APIRouter()
    processor = Processor(settings)
    indexer = Indexer(settings)
    writer = CapsuleWriter(settings)

    # Keep references to background tasks to prevent garbage collection
    background_tasks: set[asyncio.Task] = set()

    def get_capsules() -> list[dict]:
        """Load all capsules with their content."""
        return load_capsules(settings, include_content=True)

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Main dashboard page."""
        capsules = get_capsules()

        # Group by category
        by_category = defaultdict(list)
        for c in capsules:
            by_category[c.get("category", "Uncategorized")].append(c)

        # Get all unique tags
        all_tags = set()
        for c in capsules:
            all_tags.update(c.get("tags", []))

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "capsules": capsules,
                "by_category": dict(by_category),
                "categories": sorted(by_category.keys()),
                "all_tags": sorted(all_tags),
                "total": len(capsules),
                "pinned_count": sum(1 for c in capsules if c.get("pinned")),
            },
        )

    @router.get("/capsules", response_class=HTMLResponse)
    async def list_capsules(
        request: Request,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        q: Optional[str] = None,
    ):
        """HTMX: List/filter capsules."""
        capsules = get_capsules()

        # Filter by category
        if category:
            capsules = [c for c in capsules if c.get("category") == category]

        # Filter by tag
        if tag:
            capsules = [c for c in capsules if tag in c.get("tags", [])]

        # Search
        if q:
            q_lower = q.lower()
            capsules = [
                c
                for c in capsules
                if q_lower in c.get("title", "").lower()
                or q_lower in c.get("_content", "").lower()
                or any(q_lower in t.lower() for t in c.get("tags", []))
            ]

        return templates.TemplateResponse(
            "partials/capsule_list.html",
            {"request": request, "capsules": capsules},
        )

    @router.get("/capsule/{filename}", response_class=HTMLResponse)
    async def view_capsule(request: Request, filename: str):
        """HTMX: View capsule detail."""
        capsules = get_capsules()
        capsule = next((c for c in capsules if c.get("_filename") == filename), None)

        if not capsule:
            raise HTTPException(404, "Capsule not found")

        return templates.TemplateResponse(
            "partials/capsule_detail.html",
            {"request": request, "capsule": capsule},
        )

    @router.post("/capsule/{filename}/pin", response_class=HTMLResponse)
    async def toggle_pin(request: Request, filename: str):
        """HTMX: Toggle capsule pinned status."""
        md_file = find_capsule_file(settings, filename)
        if not md_file:
            raise HTTPException(404, "Capsule not found")

        post = frontmatter.load(md_file)
        post.metadata["pinned"] = not post.metadata.get("pinned", False)

        with open(md_file, "w") as f:
            f.write(frontmatter.dumps(post))

        await indexer.regenerate()

        return templates.TemplateResponse(
            "partials/pin_button.html",
            {"request": request, "pinned": post.metadata["pinned"], "filename": filename},
        )

    @router.post("/capsule/{filename}/cull", response_class=HTMLResponse)
    async def cull_capsule(request: Request, filename: str):
        """HTMX: Move capsule to Legacy."""
        md_file = find_capsule_file(settings, filename)
        if not md_file:
            raise HTTPException(404, "Capsule not found")

        writer.move_to_legacy(md_file)
        await indexer.regenerate()
        return HTMLResponse('<div class="text-gray-500">Moved to Legacy</div>')

    @router.post("/capsule/{filename}/edit", response_class=HTMLResponse)
    async def edit_capsule(
        request: Request,
        filename: str,
        title: str = Form(...),
        tags: str = Form(""),
    ):
        """HTMX: Edit capsule metadata."""
        md_file = find_capsule_file(settings, filename)
        if not md_file:
            raise HTTPException(404, "Capsule not found")

        post = frontmatter.load(md_file)
        post.metadata["title"] = title
        post.metadata["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

        with open(md_file, "w") as f:
            f.write(frontmatter.dumps(post))

        await indexer.regenerate()

        capsule = dict(post.metadata)
        capsule["_filename"] = filename
        capsule["_content"] = post.content

        return templates.TemplateResponse(
            "partials/capsule_card.html",
            {"request": request, "capsule": capsule},
        )

    # API endpoints for browser extension
    @router.get("/api/health")
    async def health():
        """Health check for extension."""
        return {"status": "ok", "version": "0.1.0"}

    @router.post("/api/capture")
    async def capture(req: CaptureRequest):
        """Capture content from browser extension (synchronous)."""
        capsule_path = await processor.process_browser_capture(
            content=req.content,
            source_url=req.source_url,
            image_data=req.image_data,
        )

        # Load the created capsule to return info
        post = frontmatter.load(capsule_path)

        return {
            "success": True,
            "title": post.metadata.get("title", "Untitled"),
            "path": str(capsule_path),
        }

    @router.post("/api/capture/async")
    async def capture_async(req: CaptureRequest):
        """Fire-and-forget capture from browser extension.

        Returns 202 Accepted immediately while processing in background.
        This enables instant popup close without waiting for LLM processing.
        """
        # Basic validation before spawning background task
        if not req.content or len(req.content.strip()) < 10:
            raise HTTPException(400, "Content too short")

        # Spawn background task with proper reference management
        # (prevents garbage collection before completion)
        task = asyncio.create_task(
            _process_capture_background(
                processor=processor,
                content=req.content,
                source_url=req.source_url,
                image_data=req.image_data,
            )
        )
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)

        # Return immediately
        return JSONResponse(
            status_code=202,
            content={"status": "queued", "message": "Processing in background"},
        )

    return router


async def _process_capture_background(
    processor: Processor,
    content: str,
    source_url: str | None,
    image_data: str | None,
):
    """Background task for processing capture.

    Runs independently after HTTP response is sent.
    """
    try:
        capsule_path = await processor.process_browser_capture(
            content=content,
            source_url=source_url,
            image_data=image_data,
        )
        logger.info(f"[BACKGROUND] Capture completed: {capsule_path.name}")
    except Exception:
        logger.exception("[BACKGROUND] Capture failed")
