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
            return

        path = Path(event.src_path)

        # Skip hidden files, temp files, and gitkeep
        if path.name.startswith(".") or path.name == ".gitkeep":
            return

        # Skip if in failed folder
        if "failed" in path.parts:
            return

        # Debounce: skip if already pending
        if str(path) in self._pending:
            return

        self._pending.add(str(path))

        # Schedule processing with delay (allow file to finish writing)
        self.loop.call_later(
            1.0,
            lambda p=path: asyncio.run_coroutine_threadsafe(
                self._process_and_cleanup(p), self.loop
            ),
        )

    async def _process_and_cleanup(self, path: Path):
        """Process file and remove from pending set."""
        try:
            if path.exists():
                await self.processor.process_file(path)
        finally:
            self._pending.discard(str(path))


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
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")
