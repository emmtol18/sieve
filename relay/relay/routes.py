"""Relay API routes."""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from . import db as db_ops
from .auth import AuthError, validate_key
from .models import CaptureIn, CaptureOut, PendingCapture

logger = logging.getLogger(__name__)


def create_router() -> APIRouter:
    """Create the relay API router."""
    router = APIRouter()

    async def _get_db(request: Request):
        """Get DB connection from app state."""
        return request.app.state.db

    async def _authenticate(request: Request) -> dict:
        """Validate Authorization header and return key record."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            raise HTTPException(401, "Unauthorized")

        db = await _get_db(request)
        try:
            return await validate_key(db, auth_header)
        except AuthError as e:
            # Use 429 for rate limits, generic 401 for all other auth failures
            if e.rate_limited:
                raise HTTPException(429, "Rate limit exceeded")
            raise HTTPException(401, "Unauthorized")

    async def _require_admin(request: Request) -> dict:
        """Authenticate and require admin key."""
        key_record = await _authenticate(request)
        if not key_record["is_admin"]:
            raise HTTPException(403, "Admin key required")
        return key_record

    @router.get("/health")
    async def health():
        """Health check (no auth required)."""
        return {"status": "ok", "service": "sieve-relay"}

    @router.post("/capture", status_code=202)
    async def capture(request: Request, body: CaptureIn):
        """Accept a capture from any valid API key."""
        key_record = await _authenticate(request)
        db = await _get_db(request)

        # Check max pending limit
        pending_count = await db_ops.count_pending(db)
        max_pending = request.app.state.settings.max_pending_captures
        if pending_count >= max_pending:
            raise HTTPException(503, "Capture queue is full")

        result = await db_ops.create_capture(
            db,
            api_key_id=key_record["id"],
            content=body.content,
            url=body.url,
            source_url=body.source_url,
            title=body.title,
            image_data=body.image_data,
        )

        logger.info(
            f"[RELAY] Capture {result['id']} from key '{key_record['name']}' "
            f"(pending: {pending_count + 1})"
        )

        return CaptureOut(
            id=result["id"],
            status=result["status"],
            created_at=result["created_at"],
        )

    @router.get("/captures/pending")
    async def get_pending(
        request: Request,
        limit: int = Query(default=100, ge=1, le=500),
    ):
        """Get pending captures (admin only)."""
        await _require_admin(request)
        db = await _get_db(request)

        rows = await db_ops.get_pending(db, limit=limit)
        captures = [PendingCapture(**row) for row in rows]

        return {"captures": captures, "count": len(captures)}

    @router.post("/captures/{capture_id}/ack")
    async def ack_capture(request: Request, capture_id: int):
        """Acknowledge a capture (admin only)."""
        await _require_admin(request)
        db = await _get_db(request)

        success = await db_ops.ack_capture(db, capture_id)
        if not success:
            raise HTTPException(404, "Capture not found or already acknowledged")

        logger.info(f"[RELAY] Capture {capture_id} acknowledged")
        return {"status": "acked", "id": capture_id}

    return router
