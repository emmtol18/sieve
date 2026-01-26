"""Process management utilities for Neural Sieve."""

import logging
import os
import signal
from pathlib import Path

logger = logging.getLogger(__name__)


class ProcessLock:
    """Manage process locks via PID files.

    Prevents duplicate service instances and enables clean shutdown.
    """

    def __init__(self, name: str, pid_dir: Path):
        """Initialize process lock.

        Args:
            name: Service name (e.g., 'coordinator')
            pid_dir: Directory for PID files
        """
        self.name = name
        self.pid_dir = pid_dir
        self.pid_file = pid_dir / f"{name}.pid"
        self._acquired = False

    def acquire(self) -> bool:
        """Acquire the lock by creating a PID file.

        Returns:
            True if lock acquired, False if already held by another process.
        """
        self.pid_dir.mkdir(parents=True, exist_ok=True)

        # Check if another process holds the lock
        existing_pid = self.get_pid()
        if existing_pid is not None:
            if self._is_process_alive(existing_pid):
                logger.warning(
                    f"[PROCESS] Lock '{self.name}' already held by PID {existing_pid}"
                )
                return False
            else:
                # Stale lock - process no longer exists
                logger.info(f"[PROCESS] Cleaning up stale lock for PID {existing_pid}")
                self._remove_pid_file()

        # Write our PID
        try:
            self.pid_file.write_text(str(os.getpid()))
            self._acquired = True
            logger.debug(f"[PROCESS] Acquired lock '{self.name}' (PID {os.getpid()})")
            return True
        except OSError as e:
            logger.error(f"[PROCESS] Failed to write PID file: {e}")
            return False

    def release(self) -> None:
        """Release the lock by removing the PID file."""
        if self._acquired:
            self._remove_pid_file()
            self._acquired = False
            logger.debug(f"[PROCESS] Released lock '{self.name}'")

    def is_locked(self) -> bool:
        """Check if the lock is held by a running process."""
        pid = self.get_pid()
        return pid is not None and self._is_process_alive(pid)

    def get_pid(self) -> int | None:
        """Get the PID from the lock file, if it exists."""
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def send_shutdown(self) -> bool:
        """Send SIGTERM to the process holding the lock.

        Returns:
            True if signal sent successfully, False otherwise.
        """
        pid = self.get_pid()
        if pid is None:
            logger.warning(f"[PROCESS] No PID found for '{self.name}'")
            return False

        if not self._is_process_alive(pid):
            logger.info(f"[PROCESS] Process {pid} not running, cleaning up lock")
            self._remove_pid_file()
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            logger.info(f"[PROCESS] Sent SIGTERM to PID {pid}")
            return True
        except OSError as e:
            logger.error(f"[PROCESS] Failed to send signal to PID {pid}: {e}")
            return False

    def _is_process_alive(self, pid: int) -> bool:
        """Check if a process is running."""
        try:
            os.kill(pid, 0)  # Signal 0 just checks if process exists
            return True
        except OSError:
            return False

    def _remove_pid_file(self) -> None:
        """Remove the PID file if it exists."""
        try:
            self.pid_file.unlink(missing_ok=True)
        except OSError:
            pass


def get_service_status(pid_dir: Path) -> dict[str, dict]:
    """Get status of all services.

    Returns:
        Dict mapping service names to status dicts with keys:
        - running: bool
        - pid: int or None
    """
    status = {}
    if not pid_dir.exists():
        return status

    for pid_file in pid_dir.glob("*.pid"):
        name = pid_file.stem
        lock = ProcessLock(name, pid_dir)
        pid = lock.get_pid()
        status[name] = {
            "running": lock.is_locked(),
            "pid": pid if lock.is_locked() else None,
        }

    return status
