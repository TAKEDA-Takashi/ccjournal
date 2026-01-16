"""Configuration management for ccjournal."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
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


@dataclass
class SyncConfig:
    """Sync configuration."""

    interval: int = 300  # seconds
    exclude_system: bool = True


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
        )

        sync = SyncConfig(
            interval=sync_data.get("interval", 300),
            exclude_system=sync_data.get("exclude_system", True),
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

[sync]
interval = {self.sync.interval}
exclude_system = {str(self.sync.exclude_system).lower()}

[projects]
# Project aliases (optional)
# "/path/to/project" = "custom-name"
'''
        for original, alias in self.project_aliases.items():
            content += f'"{original}" = "{alias}"\n'

        config_path.write_text(content)
