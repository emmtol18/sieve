"""Client for pulling captures from a remote sieve-relay server."""

import logging

import httpx

from .config import Settings
from .engine import Processor

logger = logging.getLogger(__name__)


class RelayClient:
    """Fetches pending captures from the relay and processes them locally."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.base_url = settings.relay_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {settings.relay_admin_key}",
            "Content-Type": "application/json",
        }

    async def fetch_pending(self) -> list[dict]:
        """GET /captures/pending from the relay."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.base_url}/captures/pending",
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("captures", [])

    async def ack_capture(self, capture_id: int) -> bool:
        """POST /captures/{id}/ack to mark a capture as processed."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/captures/{capture_id}/ack",
                headers=self.headers,
            )
            return resp.status_code == 200

    async def pull_and_process(self, processor: Processor) -> int:
        """Fetch pending captures, process each, and ack on success.

        Returns the number of successfully processed captures.
        """
        try:
            pending = await self.fetch_pending()
        except httpx.HTTPError as e:
            logger.error(f"[RELAY-CLIENT] Failed to fetch pending captures: {e}")
            return 0

        if not pending:
            return 0

        logger.info(f"[RELAY-CLIENT] Fetched {len(pending)} pending capture(s)")
        processed = 0

        for capture in pending:
            capture_id = capture["id"]
            try:
                await processor.process_browser_capture(
                    content=capture.get("content", ""),
                    url=capture.get("url"),
                    source_url=capture.get("source_url"),
                    image_data=capture.get("image_data"),
                )

                if await self.ack_capture(capture_id):
                    processed += 1
                    logger.info(f"[RELAY-CLIENT] Processed and acked capture {capture_id}")
                else:
                    logger.warning(f"[RELAY-CLIENT] Processed capture {capture_id} but ack failed")

            except Exception:
                logger.exception(f"[RELAY-CLIENT] Failed to process capture {capture_id}")

        return processed
