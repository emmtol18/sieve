"""Main processing pipeline."""

import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

from ..config import Settings
from ..capsule import CapsuleWriter
from ..llm import OpenAIClient
from .extractors import ImageExtractor, HTMLExtractor, TextExtractor, Extractor
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
        logger.info(f"Processing: {path.name}")

        try:
            # Find appropriate extractor
            extractor = self._get_extractor(path)
            if not extractor:
                logger.warning(f"No extractor for: {path.suffix}")
                return None

            # Extract content
            extracted = extractor.extract(path)

            # Process with LLM
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

            # Write capsule and copy asset
            original_file = extracted.image_path if extracted.is_image else None
            capsule_path = self.writer.write(capsule, original_file=original_file)

            logger.info(f"Created capsule: {capsule_path.name}")

            # Update index
            await self.indexer.regenerate()

            # Clear error count on success
            self._error_counts.pop(str(path), None)

            # Remove processed file from inbox
            try:
                if path.exists():
                    path.unlink()
            except (FileNotFoundError, PermissionError) as e:
                logger.warning(f"Could not remove source file {path.name}: {e}")

            return capsule_path

        except Exception as e:
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
            dest = self.settings.failed_path / path.name

            if dest.exists():
                stem = path.stem
                suffix = path.suffix
                counter = 1
                while dest.exists():
                    dest = self.settings.failed_path / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(path, dest)
        except (FileNotFoundError, PermissionError) as e:
            logger.warning(f"Could not move {path.name} to failed folder: {e}")

    async def process_browser_capture(
        self,
        content: str,
        source_url: str | None = None,
        image_data: str | None = None,
    ) -> Path:
        """Process content from browser extension."""
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
