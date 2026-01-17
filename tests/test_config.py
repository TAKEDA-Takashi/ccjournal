"""Tests for the config module."""

from datetime import UTC, date, datetime
from pathlib import Path

from ccjournal.config import (
    Config,
    get_last_commit_date,
    get_last_commit_date_path,
    get_last_sync,
    get_pid_file_path,
    save_last_commit_date,
    save_last_sync,
)


class TestConfig:
    """Tests for Config class."""

    def test_default_config(self) -> None:
        """Default config should have sensible defaults."""
        config = Config()

        assert config.output.structure == "date"
        assert config.output.auto_push is True
        assert config.output.remote == "origin"
        assert config.output.branch == "main"
        assert config.sync.interval == 300
        assert config.sync.exclude_system is True

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Loading nonexistent file should return defaults."""
        config = Config.load(tmp_path / "nonexistent.toml")

        assert config.output.structure == "date"

    def test_load_and_save_config(self, tmp_path: Path) -> None:
        """Config should be loadable after saving."""
        config_path = tmp_path / "config.toml"

        # Create and save config
        config = Config()
        config.output.repository = tmp_path / "logs"
        config.output.structure = "project"
        config.output.auto_push = False
        config.sync.interval = 600

        config.save(config_path)

        # Load it back
        loaded = Config.load(config_path)

        assert loaded.output.repository == tmp_path / "logs"
        assert loaded.output.structure == "project"
        assert loaded.output.auto_push is False
        assert loaded.sync.interval == 600

    def test_load_with_aliases(self, tmp_path: Path) -> None:
        """Config should load project aliases."""
        config_path = tmp_path / "config.toml"
        config_path.write_text('''
[output]
repository = "~/logs"
structure = "date"

[projects.aliases]
"/path/to/project" = "my-alias"
''')

        config = Config.load(config_path)
        assert config.output.structure == "date"


class TestLastSync:
    """Tests for last_sync functions."""

    def test_get_last_sync_nonexistent(self, tmp_path: Path) -> None:
        """get_last_sync returns None when file doesn't exist."""
        result = get_last_sync(tmp_path / "last_sync")
        assert result is None

    def test_save_and_get_last_sync(self, tmp_path: Path) -> None:
        """save_last_sync and get_last_sync should work together."""
        last_sync_path = tmp_path / "last_sync"
        now = datetime.now(UTC)

        save_last_sync(now, last_sync_path)
        result = get_last_sync(last_sync_path)

        assert result is not None
        # Compare with 1 second tolerance
        assert abs((result - now).total_seconds()) < 1

    def test_get_last_sync_invalid_content(self, tmp_path: Path) -> None:
        """get_last_sync returns None for invalid content."""
        last_sync_path = tmp_path / "last_sync"
        last_sync_path.write_text("invalid datetime")

        result = get_last_sync(last_sync_path)
        assert result is None


class TestPidFile:
    """Tests for PID file functions."""

    def test_get_pid_file_path_returns_expected_path(self) -> None:
        """get_pid_file_path returns expected path."""
        path = get_pid_file_path()
        assert path.name == "ccjournal.pid"
        assert "ccjournal" in str(path)


class TestLastCommitDate:
    """Tests for last_commit_date functions."""

    def test_get_last_commit_date_path_returns_expected_path(self) -> None:
        """get_last_commit_date_path returns expected path."""
        path = get_last_commit_date_path()
        assert path.name == "last_commit"
        assert "ccjournal" in str(path)

    def test_get_last_commit_date_nonexistent(self, tmp_path: Path) -> None:
        """get_last_commit_date returns None when file doesn't exist."""
        result = get_last_commit_date(tmp_path / "last_commit")
        assert result is None

    def test_save_and_get_last_commit_date(self, tmp_path: Path) -> None:
        """save_last_commit_date and get_last_commit_date should work together."""
        last_commit_path = tmp_path / "last_commit"
        today = date.today()

        save_last_commit_date(today, last_commit_path)
        result = get_last_commit_date(last_commit_path)

        assert result == today

    def test_get_last_commit_date_invalid_content(self, tmp_path: Path) -> None:
        """get_last_commit_date returns None for invalid content."""
        last_commit_path = tmp_path / "last_commit"
        last_commit_path.write_text("invalid date")

        result = get_last_commit_date(last_commit_path)
        assert result is None
