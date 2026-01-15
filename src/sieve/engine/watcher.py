"""File system watcher for inbox and screenshot folders."""

import asyncio
import logging
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from ..config import Settings
from .processor import Processor

logger = logging.getLogger(__name__)


class InboxHandler(FileSystemEventHandler):
    """Handles file events in watched folders."""

    def __init__(self, processor: Processor, loop: asyncio.AbstractEventLoop):
        self.processor = processor
        self.loop = loop
        self._pending: set[str] = set()

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            logger.debug(f"[WATCHER] Ignoring directory event: {event.src_path}")
            return

        path = Path(event.src_path)
        logger.debug(f"[WATCHER] File created event: {path.name}")

        # Skip hidden files, temp files, and gitkeep
        if path.name.startswith(".") or path.name == ".gitkeep":
            logger.debug(f"[WATCHER] Skipping hidden/temp file: {path.name}")
            return

        # Skip if in failed folder
        if "failed" in path.parts:
            logger.debug(f"[WATCHER] Skipping file in failed folder: {path.name}")
            return

        # Debounce: skip if already pending
        if str(path) in self._pending:
            logger.debug(f"[WATCHER] Skipping already pending file: {path.name}")
            return

        self._pending.add(str(path))
        logger.info(f"[WATCHER] Queued for processing: {path.name} (pending: {len(self._pending)})")

        # Schedule processing with delay (allow file to finish writing)
        self.loop.call_later(
            1.0,
            lambda p=path: asyncio.run_coroutine_threadsafe(
                self._process_and_cleanup(p), self.loop
            ),
        )

    async def _process_and_cleanup(self, path: Path):
        """Process file and remove from pending set."""
        logger.debug(f"[WATCHER] Starting processing: {path.name}")
        try:
            if path.exists():
                await self.processor.process_file(path)
            else:
                logger.warning(f"[WATCHER] File no longer exists: {path.name}")
        except Exception as e:
            logger.error(f"[WATCHER] Processing failed for {path.name}: {e}")
        finally:
            self._pending.discard(str(path))
            logger.debug(f"[WATCHER] Finished processing: {path.name} (pending: {len(self._pending)})")


class FileWatcher:
    """Watches inbox and screenshot folders for new files."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.observer = Observer()
        self.processor = Processor(settings)

    async def start(self):
        """Start watching folders."""
        loop = asyncio.get_running_loop()
        handler = InboxHandler(self.processor, loop)

        # Watch inbox folder
        inbox = self.settings.inbox_path
        inbox.mkdir(parents=True, exist_ok=True)
        self.observer.schedule(handler, str(inbox), recursive=False)
        logger.info(f"Watching: {inbox}")

        # Watch screenshot folder if configured
        if self.settings.screenshot_folder:
            screenshot_path = Path(self.settings.screenshot_folder).expanduser()
            if screenshot_path.exists():
                self.observer.schedule(handler, str(screenshot_path), recursive=False)
                logger.info(f"Watching screenshots: {screenshot_path}")
            else:
                logger.warning(f"Screenshot folder not found: {screenshot_path}")

        self.observer.start()
        logger.info("File watcher started")

        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            self.stop()

    def stop(self):
        """Stop watching."""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5.0)
            if self.observer.is_alive():
                logger.warning("[WATCHER] Observer thread did not stop cleanly")
        logger.info("[WATCHER] File watcher stopped")
