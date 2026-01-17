"""Tests for the daemon module."""

import os
import signal
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from ccjournal.config import Config
from ccjournal.daemon import (
    DaemonProcess,
    get_daemon_status,
    is_process_running,
    read_pid_file,
    stop_daemon,
    write_pid_file,
)


class TestPidFile:
    """Tests for PID file operations."""

    def test_write_pid_file(self, tmp_path: Path) -> None:
        """write_pid_file creates a PID file with the correct content."""
        pid_file = tmp_path / "test.pid"
        write_pid_file(pid_file, 12345)

        assert pid_file.exists()
        assert pid_file.read_text() == "12345"

    def test_read_pid_file_existing(self, tmp_path: Path) -> None:
        """read_pid_file returns the PID from an existing file."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")

        assert read_pid_file(pid_file) == 12345

    def test_read_pid_file_nonexistent(self, tmp_path: Path) -> None:
        """read_pid_file returns None for nonexistent file."""
        pid_file = tmp_path / "nonexistent.pid"

        assert read_pid_file(pid_file) is None

    def test_read_pid_file_invalid_content(self, tmp_path: Path) -> None:
        """read_pid_file returns None for invalid content."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("not a number")

        assert read_pid_file(pid_file) is None


class TestIsProcessRunning:
    """Tests for is_process_running function."""

    def test_current_process_is_running(self) -> None:
        """Current process should be reported as running."""
        assert is_process_running(os.getpid()) is True

    def test_nonexistent_process(self) -> None:
        """Nonexistent process should be reported as not running."""
        # Use a very high PID that is unlikely to exist
        assert is_process_running(999999999) is False

    def test_invalid_pid(self) -> None:
        """Invalid PID should be reported as not running."""
        assert is_process_running(-1) is False
        assert is_process_running(0) is False


class TestDaemonStatus:
    """Tests for get_daemon_status function."""

    def test_status_not_running_no_pid_file(self, tmp_path: Path) -> None:
        """Status should be not_running when no PID file exists."""
        pid_file = tmp_path / "test.pid"

        status = get_daemon_status(pid_file)

        assert status.running is False
        assert status.pid is None

    def test_status_not_running_stale_pid_file(self, tmp_path: Path) -> None:
        """Status should be not_running when PID file points to dead process."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("999999999")  # Unlikely to be a running process

        status = get_daemon_status(pid_file)

        assert status.running is False
        assert status.pid == 999999999

    def test_status_running(self, tmp_path: Path) -> None:
        """Status should be running when PID file points to live process."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text(str(os.getpid()))  # Current process

        status = get_daemon_status(pid_file)

        assert status.running is True
        assert status.pid == os.getpid()


class TestStopDaemon:
    """Tests for stop_daemon function."""

    def test_stop_daemon_no_pid_file(self, tmp_path: Path) -> None:
        """stop_daemon returns False when no PID file exists."""
        pid_file = tmp_path / "test.pid"

        result = stop_daemon(pid_file)

        assert result is False

    def test_stop_daemon_stale_pid_file(self, tmp_path: Path) -> None:
        """stop_daemon cleans up stale PID file and returns False."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("999999999")  # Unlikely to be running

        result = stop_daemon(pid_file)

        assert result is False
        assert not pid_file.exists()

    @patch("ccjournal.daemon.os.kill")
    def test_stop_daemon_running(self, mock_kill: MagicMock, tmp_path: Path) -> None:
        """stop_daemon sends SIGTERM to running process."""
        pid_file = tmp_path / "test.pid"
        pid_file.write_text("12345")

        with patch("ccjournal.daemon.is_process_running", return_value=True):
            result = stop_daemon(pid_file)

        assert result is True
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)


class TestDaemonProcess:
    """Tests for DaemonProcess class."""

    def test_daemon_process_creation(self, tmp_path: Path) -> None:
        """DaemonProcess can be created with config and paths."""
        config = Config()
        pid_file = tmp_path / "test.pid"
        last_commit_path = tmp_path / "last_commit"

        daemon = DaemonProcess(
            config=config,
            pid_file_path=pid_file,
            last_commit_path=last_commit_path,
        )

        assert daemon.config == config
        assert daemon.pid_file_path == pid_file
        assert daemon.last_commit_path == last_commit_path
        assert daemon.running is False

    def test_should_commit_first_run(self, tmp_path: Path) -> None:
        """should_commit returns True on first run (no last_commit file)."""
        config = Config()
        daemon = DaemonProcess(
            config=config,
            pid_file_path=tmp_path / "test.pid",
            last_commit_path=tmp_path / "last_commit",
        )

        assert daemon.should_commit() is True

    def test_should_commit_same_day(self, tmp_path: Path) -> None:
        """should_commit returns False if already committed today."""
        config = Config()
        last_commit_path = tmp_path / "last_commit"
        last_commit_path.write_text(date.today().isoformat())

        daemon = DaemonProcess(
            config=config,
            pid_file_path=tmp_path / "test.pid",
            last_commit_path=last_commit_path,
        )

        assert daemon.should_commit() is False

    def test_should_commit_different_day(self, tmp_path: Path) -> None:
        """should_commit returns True if last commit was on a different day."""
        config = Config()
        last_commit_path = tmp_path / "last_commit"
        # Write yesterday's date
        from datetime import timedelta

        yesterday = date.today() - timedelta(days=1)
        last_commit_path.write_text(yesterday.isoformat())

        daemon = DaemonProcess(
            config=config,
            pid_file_path=tmp_path / "test.pid",
            last_commit_path=last_commit_path,
        )

        assert daemon.should_commit() is True

    def test_stop_sets_running_false(self, tmp_path: Path) -> None:
        """stop() sets running to False."""
        config = Config()
        daemon = DaemonProcess(
            config=config,
            pid_file_path=tmp_path / "test.pid",
            last_commit_path=tmp_path / "last_commit",
        )
        daemon.running = True

        daemon.stop()

        assert daemon.running is False
