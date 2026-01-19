"""Service coordinator for running FileWatcher and Dashboard together."""

import asyncio
import logging
import signal
from typing import Optional

import uvicorn

from .config import Settings
from .dashboard import create_app
from .engine import FileWatcher

logger = logging.getLogger(__name__)


class ServiceCoordinator:
    """Coordinates FileWatcher and Dashboard services in a single process."""

    def __init__(self, settings: Settings, verbose: bool = False):
        self.settings = settings
        self.verbose = verbose
        self.watcher: Optional[FileWatcher] = None
        self.server: Optional[uvicorn.Server] = None
        self._shutdown_event = asyncio.Event()
        self._watcher_task: Optional[asyncio.Task] = None
        self._server_task: Optional[asyncio.Task] = None

    async def run(self) -> None:
        """Run both services concurrently until shutdown signal."""
        logger.info("[STARTUP] Starting Neural Sieve...")

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_signal)

        try:
            # Initialize and start services
            await self._start_services()

            logger.info("[STARTUP] All services running. Press Ctrl+C to stop.")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"[STARTUP] Fatal error: {e}")
            raise
        finally:
            await self._stop_services()

    async def _start_services(self) -> None:
        """Initialize and start both services."""
        # Initialize FileWatcher
        self.watcher = FileWatcher(self.settings)

        # Initialize uvicorn Server (non-blocking)
        app = create_app(self.settings)
        config = uvicorn.Config(
            app=app,
            host=self.settings.host,
            port=self.settings.port,
            log_level="warning",  # Suppress uvicorn's default logs
            access_log=self.verbose,
        )
        self.server = uvicorn.Server(config)

        # Start both as asyncio tasks
        self._watcher_task = asyncio.create_task(
            self._run_watcher(), name="watcher"
        )
        self._server_task = asyncio.create_task(
            self._run_server(), name="dashboard"
        )

        # Give services a moment to start
        await asyncio.sleep(0.5)

        logger.info(
            f"[DASHBOARD] Ready at http://{self.settings.host}:{self.settings.port}"
        )

    async def _run_watcher(self) -> None:
        """Run the file watcher."""
        try:
            await self.watcher.start()
        except asyncio.CancelledError:
            logger.debug("[WATCHER] Task cancelled")
            raise

    async def _run_server(self) -> None:
        """Run the uvicorn server."""
        try:
            await self.server.serve()
        except asyncio.CancelledError:
            logger.debug("[DASHBOARD] Task cancelled")
            raise

    def _handle_signal(self) -> None:
        """Handle shutdown signals (SIGINT, SIGTERM)."""
        logger.info("[STARTUP] Shutdown signal received...")
        # Use call_soon_threadsafe for thread-safe event loop interaction
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(self._shutdown_event.set)

    async def _stop_services(self) -> None:
        """Gracefully stop all services."""
        logger.info("[STARTUP] Shutting down services...")

        # Signal server to stop
        if self.server:
            try:
                self.server.should_exit = True
            except Exception as e:
                logger.error(f"[DASHBOARD] Error signaling stop: {e}")

        # Stop watcher (this joins the observer thread)
        if self.watcher:
            try:
                self.watcher.stop()
                logger.info("[WATCHER] Stopped")
            except Exception as e:
                logger.error(f"[WATCHER] Error during stop: {e}")

        # Cancel tasks if still running
        for task in [self._watcher_task, self._server_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as e:
                    logger.error(f"[STARTUP] Error cancelling task: {e}")

        logger.info("[DASHBOARD] Stopped")
        logger.info("[STARTUP] Shutdown complete")
