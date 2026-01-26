"""Tests for process management utilities."""

import os
import signal
from pathlib import Path
from unittest.mock import patch

import pytest

from sieve.process import ProcessLock, get_service_status


class TestProcessLock:
    """Tests for ProcessLock class."""

    def test_acquire_creates_pid_file(self, tmp_path: Path):
        """Lock acquisition creates a PID file."""
        lock = ProcessLock("test", tmp_path)
        assert lock.acquire() is True
        assert lock.pid_file.exists()
        assert lock.pid_file.read_text() == str(os.getpid())
        lock.release()

    def test_acquire_returns_false_if_already_locked(self, tmp_path: Path):
        """Cannot acquire lock if already held by another process."""
        lock1 = ProcessLock("test", tmp_path)
        lock2 = ProcessLock("test", tmp_path)

        assert lock1.acquire() is True
        assert lock2.acquire() is False

        lock1.release()

    def test_acquire_cleans_stale_lock(self, tmp_path: Path):
        """Stale locks (dead PIDs) are cleaned up."""
        lock = ProcessLock("test", tmp_path)

        # Write a fake PID that doesn't exist
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "test.pid").write_text("99999999")

        # Should acquire successfully (stale lock)
        assert lock.acquire() is True
        lock.release()

    def test_release_removes_pid_file(self, tmp_path: Path):
        """Release removes the PID file."""
        lock = ProcessLock("test", tmp_path)
        lock.acquire()
        assert lock.pid_file.exists()

        lock.release()
        assert not lock.pid_file.exists()

    def test_is_locked_returns_true_when_locked(self, tmp_path: Path):
        """is_locked returns True when lock is held."""
        lock = ProcessLock("test", tmp_path)
        lock.acquire()

        assert lock.is_locked() is True

        lock.release()
        assert lock.is_locked() is False

    def test_get_pid_returns_pid_from_file(self, tmp_path: Path):
        """get_pid returns the PID from the lock file."""
        lock = ProcessLock("test", tmp_path)
        lock.acquire()

        assert lock.get_pid() == os.getpid()

        lock.release()

    def test_get_pid_returns_none_if_no_file(self, tmp_path: Path):
        """get_pid returns None if no lock file exists."""
        lock = ProcessLock("test", tmp_path)
        assert lock.get_pid() is None

    def test_send_shutdown_sends_sigterm(self, tmp_path: Path):
        """send_shutdown sends SIGTERM to the process."""
        lock = ProcessLock("test", tmp_path)
        lock.acquire()

        # Mock os.kill to avoid actually sending signal
        with patch("os.kill") as mock_kill:
            assert lock.send_shutdown() is True
            # First call is to check if process is alive (signal 0)
            # Second call is the actual SIGTERM
            assert mock_kill.call_count == 2
            mock_kill.assert_any_call(os.getpid(), 0)
            mock_kill.assert_any_call(os.getpid(), signal.SIGTERM)

        lock.release()

    def test_send_shutdown_returns_false_if_no_pid(self, tmp_path: Path):
        """send_shutdown returns False if no lock file exists."""
        lock = ProcessLock("test", tmp_path)
        assert lock.send_shutdown() is False


class TestGetServiceStatus:
    """Tests for get_service_status function."""

    def test_returns_empty_dict_if_no_pid_dir(self, tmp_path: Path):
        """Returns empty dict if PID directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"
        assert get_service_status(nonexistent) == {}

    def test_returns_status_for_running_service(self, tmp_path: Path):
        """Returns running status for active service."""
        lock = ProcessLock("coordinator", tmp_path)
        lock.acquire()

        status = get_service_status(tmp_path)
        assert "coordinator" in status
        assert status["coordinator"]["running"] is True
        assert status["coordinator"]["pid"] == os.getpid()

        lock.release()

    def test_returns_not_running_for_stale_lock(self, tmp_path: Path):
        """Returns not running for stale lock file."""
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "coordinator.pid").write_text("99999999")

        status = get_service_status(tmp_path)
        assert "coordinator" in status
        assert status["coordinator"]["running"] is False
        assert status["coordinator"]["pid"] is None
