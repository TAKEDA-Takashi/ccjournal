"""Daemon process for ccjournal."""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import FrameType

from .config import (
    Config,
    get_last_commit_date,
    get_last_commit_date_path,
    get_last_sync,
    get_pid_file_path,
    save_last_commit_date,
    save_last_sync,
)
from .sync import (
    check_push_permission,
    git_commit_and_push,
    sync_logs,
)


def write_pid_file(path: Path, pid: int) -> None:
    """Write PID to file.

    Args:
        path: Path to the PID file.
        pid: Process ID to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def read_pid_file(path: Path) -> int | None:
    """Read PID from file.

    Args:
        path: Path to the PID file.

    Returns:
        Process ID if file exists and contains valid content, None otherwise.
    """
    if not path.exists():
        return None

    try:
        return int(path.read_text().strip())
    except (ValueError, OSError):
        return None


def is_process_running(pid: int) -> bool:
    """Check if a process is running.

    Args:
        pid: Process ID to check.

    Returns:
        True if process is running, False otherwise.
    """
    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@dataclass
class DaemonStatus:
    """Status of the daemon process."""

    running: bool
    pid: int | None
    last_sync: datetime | None = None
    last_commit: date | None = None


def get_daemon_status(
    pid_file_path: Path | None = None,
    last_sync_path: Path | None = None,
    last_commit_path: Path | None = None,
) -> DaemonStatus:
    """Get the status of the daemon.

    Args:
        pid_file_path: Path to the PID file.
        last_sync_path: Path to the last sync timestamp file.
        last_commit_path: Path to the last commit date file.

    Returns:
        DaemonStatus with running state and metadata.
    """
    pid_path = pid_file_path or get_pid_file_path()
    pid = read_pid_file(pid_path)

    running = pid is not None and is_process_running(pid)
    last_sync = get_last_sync(last_sync_path)
    last_commit = get_last_commit_date(last_commit_path)

    return DaemonStatus(
        running=running,
        pid=pid,
        last_sync=last_sync,
        last_commit=last_commit,
    )


def stop_daemon(pid_file_path: Path | None = None, timeout: float = 5.0) -> bool:
    """Stop the daemon.

    Args:
        pid_file_path: Path to the PID file.
        timeout: Maximum time to wait for process to stop (seconds).

    Returns:
        True if daemon was stopped, False if not running.
    """
    pid_path = pid_file_path or get_pid_file_path()
    pid = read_pid_file(pid_path)

    if pid is None:
        return False

    if not is_process_running(pid):
        # Clean up stale PID file
        pid_path.unlink(missing_ok=True)
        return False

    os.kill(pid, signal.SIGTERM)

    # Wait for process to stop
    wait_time = 0.0
    while wait_time < timeout and is_process_running(pid):
        time.sleep(0.1)
        wait_time += 0.1

    return True


class DaemonProcess:
    """Daemon process for periodic sync.

    Attributes:
        config: Application configuration.
        pid_file_path: Path to store the PID file.
        last_commit_path: Path to store the last commit date.
        running: Whether the daemon is running.
    """

    def __init__(
        self,
        config: Config,
        pid_file_path: Path | None = None,
        last_commit_path: Path | None = None,
        log_path: Path | None = None,
    ) -> None:
        """Initialize the daemon process.

        Args:
            config: Application configuration.
            pid_file_path: Path to store the PID file.
            last_commit_path: Path to store the last commit date.
            log_path: Path to the log file.
        """
        self.config = config
        self.pid_file_path = pid_file_path or get_pid_file_path()
        self.last_commit_path = last_commit_path or get_last_commit_date_path()
        self.log_path = log_path
        self.running = False
        self._logger: logging.Logger | None = None

    def _setup_logging(self) -> None:
        """Set up logging for the daemon."""
        self._logger = logging.getLogger("ccjournal.daemon")
        self._logger.setLevel(logging.INFO)

        handler: logging.Handler = (
            logging.FileHandler(self.log_path)
            if self.log_path
            else logging.StreamHandler()
        )

        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def _log(self, message: str, level: int = logging.INFO) -> None:
        """Log a message."""
        if self._logger:
            self._logger.log(level, message)

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum: int, _frame: FrameType | None) -> None:
            self._log(f"Received signal {signum}, stopping...")
            self.stop()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def should_commit(self) -> bool:
        """Check if a commit should be made.

        Commits are made once per day, on the first sync after midnight.

        Returns:
            True if a commit should be made, False otherwise.
        """
        last_commit = get_last_commit_date(self.last_commit_path)
        today = date.today()

        return last_commit is None or last_commit != today

    def _check_push_allowed(self) -> bool:
        """Check if pushing to remote is allowed based on repository visibility.

        Returns:
            True if push is allowed, False otherwise.
        """
        if not self.config.output.auto_push:
            return True  # Push is disabled anyway

        result = check_push_permission(
            self.config.output.repository,
            allow_public=self.config.output.allow_public_repository,
            allow_unknown=self.config.output.allow_unknown_visibility,
        )

        if not result.allowed:
            self._log(result.warning_message or "Push not allowed", logging.ERROR)
            return False

        if result.warning_message:
            self._log(result.warning_message, logging.WARNING)

        return True

    def _do_sync(self) -> None:
        """Perform a single sync cycle."""
        try:
            since = get_last_sync()
            if since:
                self._log(f"Syncing files modified since {since.isoformat()}")

            written_paths = sync_logs(self.config, since=since)

            if written_paths:
                self._log(f"Wrote {len(written_paths)} file(s)")
                save_last_sync(datetime.now(UTC))

                # Commit once per day
                if self.should_commit():
                    should_push = self._check_push_allowed()
                    self._log("Committing changes (daily commit)")
                    success = git_commit_and_push(
                        self.config.output.repository,
                        self.config.output.remote,
                        self.config.output.branch,
                        auto_push=self.config.output.auto_push and should_push,
                    )
                    if success:
                        save_last_commit_date(date.today(), self.last_commit_path)
                        self._log("Commit successful")
                    else:
                        self._log("Commit failed", logging.ERROR)
            else:
                self._log("No logs to sync", logging.DEBUG)

        except Exception as e:
            self._log(f"Sync error: {e}", logging.ERROR)

    def stop(self) -> None:
        """Stop the daemon."""
        self.running = False

    def run(self) -> None:
        """Run the daemon main loop."""
        self._setup_logging()
        self._setup_signal_handlers()

        # Write PID file
        write_pid_file(self.pid_file_path, os.getpid())
        self._log(f"Daemon started (PID: {os.getpid()})")

        self.running = True
        interval = self.config.sync.interval

        try:
            while self.running:
                self._do_sync()

                # Sleep in small increments to allow for signal handling
                sleep_time = 0
                while sleep_time < interval and self.running:
                    time.sleep(min(1, interval - sleep_time))
                    sleep_time += 1
        finally:
            # Clean up PID file
            self.pid_file_path.unlink(missing_ok=True)
            self._log("Daemon stopped")


def daemonize() -> None:
    """Detach from terminal using Unix double-fork."""
    # First fork
    pid = os.fork()
    if pid > 0:
        # Parent exits
        sys.exit(0)

    # Create new session
    os.setsid()

    # Second fork
    pid = os.fork()
    if pid > 0:
        # First child exits
        sys.exit(0)

    # Redirect standard file descriptors
    sys.stdin.close()
    sys.stdout.close()
    sys.stderr.close()

    # Open null device for standard streams
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)


def start_daemon(config: Config, foreground: bool = False) -> bool:
    """Start the daemon process.

    Args:
        config: Application configuration.
        foreground: If True, run in foreground instead of daemonizing.

    Returns:
        True if daemon was started successfully.
    """
    pid_path = get_pid_file_path()
    status = get_daemon_status(pid_path)

    if status.running:
        return False  # Already running

    log_path = pid_path.parent / "daemon.log"

    if not foreground:
        daemonize()

    daemon = DaemonProcess(
        config=config,
        pid_file_path=pid_path,
        log_path=log_path if not foreground else None,
    )
    daemon.run()

    return True
