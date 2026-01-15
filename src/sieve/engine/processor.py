"""Main processing pipeline."""

import asyncio
import ipaddress
import logging
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from ..capsule import CapsuleWriter
from ..config import Settings
from ..llm import OpenAIClient
from ..utils import get_unique_path
from .extractors import Extractor, HTMLExtractor, ImageExtractor, TextExtractor
from .indexer import Indexer

logger = logging.getLogger(__name__)


class Processor:
    """Orchestrates the processing pipeline: extract -> LLM -> capsule."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = OpenAIClient(settings)
        self.writer = CapsuleWriter(settings)
        self.indexer = Indexer(settings)
        self.extractors: list[Extractor] = [
            ImageExtractor(),
            HTMLExtractor(),
            TextExtractor(),
        ]
        self._error_counts: dict[str, int] = {}

    def _get_extractor(self, path: Path) -> Extractor | None:
        """Find an extractor that can handle this file."""
        for extractor in self.extractors:
            if extractor.can_handle(path):
                return extractor
        return None

    async def process_file(self, path: Path, capture_method: str = "drop") -> Path | None:
        """Process a file through the pipeline.

        Returns the path to the created capsule, or None if failed.
        """
        logger.info(f"[PROCESSOR] Starting: {path.name} (size: {path.stat().st_size} bytes)")

        try:
            # Find appropriate extractor
            extractor = self._get_extractor(path)
            if not extractor:
                logger.warning(f"[PROCESSOR] No extractor for: {path.suffix}")
                return None

            extractor_name = extractor.__class__.__name__
            logger.debug(f"[PROCESSOR] Using extractor: {extractor_name}")

            # Extract content
            logger.debug(f"[PROCESSOR] Extracting content from: {path.name}")
            extracted = extractor.extract(path)

            if extracted.is_image:
                logger.debug(f"[PROCESSOR] Extracted image: {extracted.image_path}")
            else:
                content_preview = (extracted.text or "")[:100].replace("\n", " ")
                logger.debug(f"[PROCESSOR] Extracted text ({len(extracted.text or '')} chars): {content_preview}...")

            # Process with LLM
            logger.info(f"[PROCESSOR] Calling LLM for: {path.name}")
            if extracted.is_image:
                capsule = await self.llm.process_image(
                    extracted.image_path,
                    capture_method=capture_method,
                )
            else:
                capsule = await self.llm.process_text(
                    extracted.text,
                    source_url=extracted.source_url,
                    capture_method=capture_method,
                )

            logger.debug(f"[PROCESSOR] LLM returned capsule: {capsule.metadata.title}")

            # Write capsule and copy asset
            original_file = extracted.image_path if extracted.is_image else None
            logger.debug(f"[PROCESSOR] Writing capsule to disk...")
            capsule_path = self.writer.write(capsule, original_file=original_file)

            logger.info(f"[PROCESSOR] Created capsule: {capsule_path.name} (category: {capsule.metadata.category})")

            # Update index
            logger.debug(f"[PROCESSOR] Regenerating index...")
            await self.indexer.regenerate()

            # Clear error count on success
            self._error_counts.pop(str(path), None)

            # Remove processed file from inbox
            try:
                if path.exists():
                    path.unlink()
                    logger.debug(f"[PROCESSOR] Removed source file: {path.name}")
            except (FileNotFoundError, PermissionError) as e:
                logger.warning(f"[PROCESSOR] Could not remove source file {path.name}: {e}")

            logger.info(f"[PROCESSOR] Completed: {path.name} -> {capsule_path.name}")
            return capsule_path

        except Exception as e:
            logger.error(f"[PROCESSOR] Error processing {path.name}: {type(e).__name__}: {e}")
            return await self._handle_error(path, e)

    async def _handle_error(self, path: Path, error: Exception) -> None:
        """Handle processing error with retry tracking."""
        path_str = str(path)
        self._error_counts[path_str] = self._error_counts.get(path_str, 0) + 1
        count = self._error_counts[path_str]

        logger.error(f"Error processing {path.name} (attempt {count}): {error}")

        # Log to error file
        self._log_error(path, error)

        if count >= self.settings.max_retries:
            # Move to failed folder
            self._move_to_failed(path)
            self._error_counts.pop(path_str, None)
            logger.error(f"Max retries reached, moved to failed: {path.name}")

        return None

    def _log_error(self, path: Path, error: Exception):
        """Append error to log file."""
        self.settings.sieve_path.mkdir(parents=True, exist_ok=True)
        with open(self.settings.error_log_path, "a") as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {path.name}: {error}\n")

    def _move_to_failed(self, path: Path):
        """Move file to failed folder."""
        try:
            if not path.exists():
                return

            self.settings.failed_path.mkdir(parents=True, exist_ok=True)
            dest = get_unique_path(self.settings.failed_path / path.name)
            shutil.move(path, dest)
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"Could not move {path.name} to failed folder: {e}")

    async def process_browser_capture(
        self,
        content: str = "",
        url: str | None = None,
        source_url: str | None = None,
        image_data: str | None = None,
    ) -> Path:
        """Process content from browser extension.

        Args:
            content: Direct text content (for selection/full page capture)
            url: URL to fetch and process (for URL capture)
            source_url: Original page URL for attribution
            image_data: Base64 encoded image
        """
        # If URL provided, fetch and extract content
        if url:
            logger.info(f"[PROCESSOR] Fetching URL: {url}")
            try:
                html, final_url = await self._fetch_url(url)
            except httpx.TimeoutException:
                logger.error(f"[PROCESSOR] URL fetch timeout: {url}")
                raise ValueError(f"Request timeout while fetching URL")
            except httpx.HTTPStatusError as e:
                logger.error(f"[PROCESSOR] HTTP error {e.response.status_code}: {url}")
                raise ValueError(f"Failed to fetch URL (HTTP {e.response.status_code})")
            except httpx.RequestError as e:
                logger.error(f"[PROCESSOR] Network error fetching {url}: {e}")
                raise ValueError(f"Network error fetching URL")

            # Extract text from HTML
            extractor = HTMLExtractor()
            extracted = extractor.extract_from_string(html)
            content = extracted.text or ""

            # Validate extracted content has substance
            if len(content.strip()) < 50:
                logger.error(f"[PROCESSOR] Insufficient content extracted from {url}")
                raise ValueError(f"Could not extract meaningful content from URL")

            # Use extracted source_url or final URL
            if not source_url:
                source_url = extracted.source_url or final_url

            logger.info(f"[PROCESSOR] Extracted {len(content)} chars from URL")

        if image_data:
            capsule = await self.llm.process_image_base64(
                image_data,
                source_url=source_url,
                capture_method="browser",
            )
        else:
            capsule = await self.llm.process_text(
                content,
                source_url=source_url,
                capture_method="browser",
            )

        capsule_path = self.writer.write(capsule)
        await self.indexer.regenerate()

        return capsule_path

    def _validate_url(self, url: str) -> None:
        """Validate URL to prevent SSRF attacks.

        Raises:
            ValueError: If URL is invalid or targets internal resources
        """
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

        hostname = parsed.hostname
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")

        # Block localhost variations
        blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"}
        if hostname.lower() in blocked_hosts:
            raise ValueError(f"Access to internal resources is blocked")

        # Block private IP ranges
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"Access to private IP addresses is blocked")
        except ValueError:
            # Not an IP address, hostname is fine
            pass

    async def _fetch_url(self, url: str, timeout: int = 30) -> tuple[str, str]:
        """Fetch HTML content from a URL.

        Returns:
            Tuple of (html_content, final_url_after_redirects)

        Raises:
            ValueError: If URL is invalid or targets internal resources
            httpx.HTTPError: If request fails
        """
        # Validate URL before fetching
        self._validate_url(url)

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()

            final_url = str(response.url)
            html_content = response.text

            logger.info(f"[PROCESSOR] Fetched {len(html_content)} bytes from {final_url}")
            return html_content, final_url
