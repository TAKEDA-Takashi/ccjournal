"""Configuration management for ccjournal."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal


def get_default_config_path() -> Path:
    """Get the default configuration file path."""
    return Path.home() / ".config" / "ccjournal" / "config.toml"


def get_claude_projects_path() -> Path:
    """Get the Claude Code projects directory path."""
    return Path.home() / ".claude" / "projects"


@dataclass
class OutputConfig:
    """Output configuration."""

    repository: Path = field(default_factory=lambda: Path.home() / "Documents" / "claude-logs")
    structure: Literal["date", "project"] = "date"
    remote: str = "origin"
    branch: str = "main"
    auto_push: bool = True
    allow_public_repository: bool = False
    allow_unknown_visibility: bool = False


@dataclass
class SyncConfig:
    """Sync configuration."""

    interval: int = 300  # seconds
    exclude_system: bool = True
    exclude_tool_messages: bool = True


@dataclass
class Config:
    """Application configuration."""

    output: OutputConfig = field(default_factory=OutputConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    project_aliases: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load configuration from TOML file."""
        config_path = path or get_default_config_path()

        if not config_path.exists():
            return cls()

        with config_path.open("rb") as f:
            data = tomllib.load(f)

        output_data = data.get("output", {})
        sync_data = data.get("sync", {})
        aliases = data.get("projects", {}).get("aliases", {})

        output = OutputConfig(
            repository=Path(output_data.get("repository", OutputConfig().repository)).expanduser(),
            structure=output_data.get("structure", "date"),
            remote=output_data.get("remote", "origin"),
            branch=output_data.get("branch", "main"),
            auto_push=output_data.get("auto_push", True),
            allow_public_repository=output_data.get("allow_public_repository", False),
            allow_unknown_visibility=output_data.get("allow_unknown_visibility", False),
        )

        sync = SyncConfig(
            interval=sync_data.get("interval", 300),
            exclude_system=sync_data.get("exclude_system", True),
            exclude_tool_messages=sync_data.get("exclude_tool_messages", True),
        )

        return cls(output=output, sync=sync, project_aliases=aliases)

    def save(self, path: Path | None = None) -> None:
        """Save configuration to TOML file."""
        config_path = path or get_default_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)

        content = f'''[output]
repository = "{self.output.repository}"
structure = "{self.output.structure}"
remote = "{self.output.remote}"
branch = "{self.output.branch}"
auto_push = {str(self.output.auto_push).lower()}
# Security: Set to true only if you understand the risks of pushing logs to a public repository
allow_public_repository = {str(self.output.allow_public_repository).lower()}
# Security: Set to true to allow pushing when repository visibility cannot be determined
# (e.g., non-GitHub repositories or when gh CLI is not available)
allow_unknown_visibility = {str(self.output.allow_unknown_visibility).lower()}

[sync]
interval = {self.sync.interval}
exclude_system = {str(self.sync.exclude_system).lower()}
exclude_tool_messages = {str(self.sync.exclude_tool_messages).lower()}

[projects]
# Project aliases (optional)
# "/path/to/project" = "custom-name"
'''
        for original, alias in self.project_aliases.items():
            content += f'"{original}" = "{alias}"\n'

        config_path.write_text(content)


def get_default_last_sync_path() -> Path:
    """Get the default last sync file path."""
    return Path.home() / ".config" / "ccjournal" / "last_sync"


def get_last_sync(path: Path | None = None) -> datetime | None:
    """Get the last sync timestamp.

    Args:
        path: Path to the last sync file. If None, uses default path.

    Returns:
        The last sync datetime, or None if not found or invalid.
    """
    last_sync_path = path or get_default_last_sync_path()

    if not last_sync_path.exists():
        return None

    try:
        content = last_sync_path.read_text().strip()
        return datetime.fromisoformat(content)
    except (ValueError, OSError):
        return None


def save_last_sync(timestamp: datetime, path: Path | None = None) -> None:
    """Save the last sync timestamp.

    Args:
        timestamp: The timestamp to save.
        path: Path to the last sync file. If None, uses default path.
    """
    last_sync_path = path or get_default_last_sync_path()
    last_sync_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure timezone-aware datetime is saved in ISO format
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    last_sync_path.write_text(timestamp.isoformat())


def get_pid_file_path() -> Path:
    """Get the default PID file path."""
    return Path.home() / ".config" / "ccjournal" / "ccjournal.pid"


def get_last_commit_date_path() -> Path:
    """Get the default last commit date file path."""
    return Path.home() / ".config" / "ccjournal" / "last_commit"


def get_last_commit_date(path: Path | None = None) -> date | None:
    """Get the last commit date.

    Args:
        path: Path to the last commit file. If None, uses default path.

    Returns:
        The last commit date, or None if not found or invalid.
    """
    last_commit_path = path or get_last_commit_date_path()

    if not last_commit_path.exists():
        return None

    try:
        content = last_commit_path.read_text().strip()
        return date.fromisoformat(content)
    except (ValueError, OSError):
        return None


def save_last_commit_date(commit_date: date, path: Path | None = None) -> None:
    """Save the last commit date.

    Args:
        commit_date: The date to save.
        path: Path to the last commit file. If None, uses default path.
    """
    last_commit_path = path or get_last_commit_date_path()
    last_commit_path.parent.mkdir(parents=True, exist_ok=True)

    last_commit_path.write_text(commit_date.isoformat())
