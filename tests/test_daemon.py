"""Tests for the daemon module."""

import os
import signal
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from ccjournal.config import Config
from ccjournal.daemon import (
    DaemonProcess,
    generate_launchd_plist,
    generate_systemd_service,
    get_daemon_status,
    get_default_log_path,
    get_launchd_plist_path,
    get_systemd_service_path,
    is_process_running,
    read_pid_file,
    stop_daemon,
    uninstall_service,
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


class TestServicePaths:
    """Tests for service path functions."""

    def test_get_launchd_plist_path_user(self) -> None:
        """get_launchd_plist_path returns user LaunchAgents path for user=True."""
        path = get_launchd_plist_path(user=True)

        assert path.name == "com.ccjournal.daemon.plist"
        assert "LaunchAgents" in str(path)

    def test_get_launchd_plist_path_system(self) -> None:
        """get_launchd_plist_path returns system LaunchDaemons path for user=False."""
        path = get_launchd_plist_path(user=False)

        assert path.name == "com.ccjournal.daemon.plist"
        assert path == Path("/Library/LaunchDaemons/com.ccjournal.daemon.plist")

    def test_get_systemd_service_path_user(self) -> None:
        """get_systemd_service_path returns user systemd path for user=True."""
        path = get_systemd_service_path(user=True)

        assert path.name == "ccjournal.service"
        assert ".config/systemd/user" in str(path)

    def test_get_systemd_service_path_system(self) -> None:
        """get_systemd_service_path returns system systemd path for user=False."""
        path = get_systemd_service_path(user=False)

        assert path == Path("/etc/systemd/system/ccjournal.service")

    def test_get_default_log_path(self) -> None:
        """get_default_log_path returns expected path."""
        path = get_default_log_path()

        assert path.name == "daemon.log"
        assert ".config/ccjournal" in str(path)


class TestGenerateLaunchdPlist:
    """Tests for generate_launchd_plist function."""

    def test_generates_valid_xml(self) -> None:
        """generate_launchd_plist generates valid XML plist."""
        ccjournal_path = "/usr/local/bin/ccjournal"
        log_path = Path("/Users/test/.config/ccjournal/daemon.log")

        content = generate_launchd_plist(ccjournal_path, log_path)

        assert '<?xml version="1.0" encoding="UTF-8"?>' in content
        assert "<!DOCTYPE plist" in content
        assert '<plist version="1.0">' in content

    def test_contains_label(self) -> None:
        """generate_launchd_plist includes correct label."""
        content = generate_launchd_plist("/bin/ccjournal", Path("/tmp/log"))

        assert "<key>Label</key>" in content
        assert "<string>com.ccjournal.daemon</string>" in content

    def test_contains_program_arguments(self) -> None:
        """generate_launchd_plist includes program arguments."""
        ccjournal_path = "/opt/bin/ccjournal"
        content = generate_launchd_plist(ccjournal_path, Path("/tmp/log"))

        assert "<key>ProgramArguments</key>" in content
        assert f"<string>{ccjournal_path}</string>" in content
        assert "<string>daemon</string>" in content
        assert "<string>start</string>" in content
        assert "<string>--foreground</string>" in content

    def test_contains_run_at_load(self) -> None:
        """generate_launchd_plist sets RunAtLoad to true."""
        content = generate_launchd_plist("/bin/ccjournal", Path("/tmp/log"))

        assert "<key>RunAtLoad</key>" in content
        assert "<true/>" in content

    def test_contains_keep_alive(self) -> None:
        """generate_launchd_plist sets KeepAlive to true."""
        content = generate_launchd_plist("/bin/ccjournal", Path("/tmp/log"))

        assert "<key>KeepAlive</key>" in content

    def test_contains_log_paths(self) -> None:
        """generate_launchd_plist includes log paths."""
        log_path = Path("/Users/test/.config/ccjournal/daemon.log")
        content = generate_launchd_plist("/bin/ccjournal", log_path)

        assert "<key>StandardOutPath</key>" in content
        assert "<key>StandardErrorPath</key>" in content
        assert f"<string>{log_path}</string>" in content


class TestGenerateSystemdService:
    """Tests for generate_systemd_service function."""

    def test_contains_unit_section(self) -> None:
        """generate_systemd_service includes Unit section."""
        content = generate_systemd_service("/bin/ccjournal", Path("/tmp/log"))

        assert "[Unit]" in content
        assert "Description=ccjournal" in content
        assert "After=network.target" in content

    def test_contains_service_section(self) -> None:
        """generate_systemd_service includes Service section."""
        ccjournal_path = "/opt/bin/ccjournal"
        content = generate_systemd_service(ccjournal_path, Path("/tmp/log"))

        assert "[Service]" in content
        assert "Type=simple" in content
        assert f"ExecStart={ccjournal_path} daemon start --foreground" in content
        assert "Restart=on-failure" in content
        assert "RestartSec=10" in content

    def test_contains_install_section(self) -> None:
        """generate_systemd_service includes Install section."""
        content = generate_systemd_service("/bin/ccjournal", Path("/tmp/log"))

        assert "[Install]" in content
        assert "WantedBy=default.target" in content

    def test_contains_log_paths(self) -> None:
        """generate_systemd_service includes log paths."""
        log_path = Path("/home/user/.config/ccjournal/daemon.log")
        content = generate_systemd_service("/bin/ccjournal", log_path)

        assert f"StandardOutput=append:{log_path}" in content
        assert f"StandardError=append:{log_path}" in content

    def test_different_paths_produce_different_content(self) -> None:
        """generate_systemd_service produces different content for different paths."""
        content1 = generate_systemd_service("/path/one", Path("/log/one"))
        content2 = generate_systemd_service("/path/two", Path("/log/two"))

        assert content1 != content2
        assert "/path/one" in content1
        assert "/path/two" in content2


class TestUninstallService:
    """Tests for uninstall_service function."""

    def test_uninstall_removes_existing_file(self, tmp_path: Path) -> None:
        """uninstall_service removes the service file if it exists."""
        service_file = tmp_path / "test.plist"
        service_file.write_text("dummy content")

        result = uninstall_service(service_file)

        assert result is True
        assert not service_file.exists()

    def test_uninstall_nonexistent_file(self, tmp_path: Path) -> None:
        """uninstall_service returns False if file doesn't exist."""
        service_file = tmp_path / "nonexistent.plist"

        result = uninstall_service(service_file)

        assert result is False

    def test_uninstall_returns_removed_path(self, tmp_path: Path) -> None:
        """uninstall_service removes the correct file."""
        service_file = tmp_path / "service.plist"
        service_file.write_text("content")
        other_file = tmp_path / "other.txt"
        other_file.write_text("other")

        uninstall_service(service_file)

        assert not service_file.exists()
        assert other_file.exists()
