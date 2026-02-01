"""Service coordinator for running FileWatcher and Dashboard together."""

import asyncio
import logging
import signal
import sys
from typing import Optional

import uvicorn

from .config import Settings
from .dashboard import create_app
from .engine import FileWatcher
from .process import ProcessLock

logger = logging.getLogger(__name__)


class ServiceCoordinator:
    """Coordinates FileWatcher and Dashboard services in a single process."""

    def __init__(self, settings: Settings, verbose: bool = False, daemon: bool = False):
        self.settings = settings
        self.verbose = verbose
        self.daemon = daemon
        self.watcher: Optional[FileWatcher] = None
        self.server: Optional[uvicorn.Server] = None
        self._shutdown_event = asyncio.Event()
        self._watcher_task: Optional[asyncio.Task] = None
        self._server_task: Optional[asyncio.Task] = None
        self._relay_task: Optional[asyncio.Task] = None
        self._process_lock: Optional[ProcessLock] = None

    async def run(self) -> None:
        """Run both services concurrently until shutdown signal."""
        # Acquire process lock to prevent duplicate instances
        self._process_lock = ProcessLock("coordinator", self.settings.pid_dir)
        if not self._process_lock.acquire():
            existing_pid = self._process_lock.get_pid()
            logger.error(
                f"[STARTUP] Another instance is already running (PID {existing_pid}). "
                "Use 'sieve stop' to stop it first, or 'sieve status' to check."
            )
            sys.exit(1)

        logger.info("[STARTUP] Starting Neural Sieve...")

        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_signal)

        try:
            # Initialize and start services
            await self._start_services()

            if self.daemon:
                logger.info("[STARTUP] Running as daemon. Use 'sieve stop' to stop.")
            else:
                logger.info("[STARTUP] All services running. Press Ctrl+C to stop.")

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        except Exception as e:
            logger.error(f"[STARTUP] Fatal error: {e}")
            raise
        finally:
            await self._stop_services()
            if self._process_lock:
                self._process_lock.release()

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

        # Start core services as asyncio tasks
        self._watcher_task = asyncio.create_task(
            self._run_watcher(), name="watcher"
        )
        self._server_task = asyncio.create_task(
            self._run_server(), name="dashboard"
        )

        # Start relay pull loop if configured
        if self.settings.relay_url and self.settings.relay_admin_key:
            self._relay_task = asyncio.create_task(
                self._run_relay_pull(), name="relay-pull"
            )
            logger.info(f"[RELAY-CLIENT] Pull loop started (interval: {self.settings.relay_pull_interval}s)")

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

    async def _run_relay_pull(self) -> None:
        """Periodically pull captures from the remote relay."""
        from .engine import Processor
        from .relay_client import RelayClient

        client = RelayClient(self.settings)
        processor = Processor(self.settings)

        try:
            while not self._shutdown_event.is_set():
                try:
                    count = await client.pull_and_process(processor)
                    if count:
                        logger.info(f"[RELAY-CLIENT] Pulled and processed {count} capture(s)")
                except Exception:
                    logger.exception("[RELAY-CLIENT] Error during pull cycle")

                # Wait for interval or shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self.settings.relay_pull_interval,
                    )
                    break  # Shutdown event set
                except asyncio.TimeoutError:
                    pass  # Interval elapsed, loop again
        except asyncio.CancelledError:
            logger.debug("[RELAY-CLIENT] Task cancelled")
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
        for task in [self._watcher_task, self._server_task, self._relay_task]:
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
