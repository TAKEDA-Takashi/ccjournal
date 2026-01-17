"""Sync logic for ccjournal."""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from .config import Config, get_claude_projects_path
from .parser import (
    Message,
    decode_project_path,
    extract_project_name,
    get_git_branch,
    parse_session_file,
)


class RepositoryVisibility(Enum):
    """Repository visibility status."""

    PUBLIC = "public"
    PRIVATE = "private"
    UNKNOWN = "unknown"


class PublicRepositoryError(Exception):
    """Error raised when attempting to push to a public repository without explicit permission."""

    def __init__(self, repo_path: Path) -> None:
        self.repo_path = repo_path
        super().__init__(
            f"Refusing to push to public repository: {repo_path}\n"
            f"Session logs may contain sensitive information.\n"
            f"To allow pushing to a public repository, set 'allow_public_repository = true' "
            f"in your config file (~/.config/ccjournal/config.toml)."
        )


@dataclass
class PushPermissionResult:
    """Result of push permission check."""

    allowed: bool
    visibility: RepositoryVisibility
    warning_message: str | None = None


def check_push_permission(
    repo_path: Path,
    allow_public: bool,
    allow_unknown: bool,
) -> PushPermissionResult:
    """Check if pushing to remote is allowed based on repository visibility.

    Args:
        repo_path: Path to the repository
        allow_public: Whether pushing to public repositories is allowed
        allow_unknown: Whether pushing when visibility is unknown is allowed

    Returns:
        PushPermissionResult with allowed status, visibility, and optional warning
    """
    visibility = check_repository_visibility(repo_path)

    if visibility == RepositoryVisibility.PUBLIC:
        if not allow_public:
            return PushPermissionResult(
                allowed=False,
                visibility=visibility,
                warning_message=(
                    "Refusing to push to public repository. "
                    "Set 'allow_public_repository = true' to override."
                ),
            )
        return PushPermissionResult(
            allowed=True,
            visibility=visibility,
            warning_message=(
                "Pushing to a PUBLIC repository. "
                "Ensure no sensitive information is included."
            ),
        )

    if visibility == RepositoryVisibility.UNKNOWN:
        if not allow_unknown:
            return PushPermissionResult(
                allowed=False,
                visibility=visibility,
                warning_message=(
                    "Repository visibility unknown (non-GitHub or gh CLI not available). "
                    "Set 'allow_unknown_visibility = true' to push anyway."
                ),
            )
        return PushPermissionResult(
            allowed=True,
            visibility=visibility,
            warning_message="Repository visibility unknown. Proceeding with push.",
        )

    # PRIVATE - always allowed
    return PushPermissionResult(allowed=True, visibility=visibility)


def check_repository_visibility(repo_path: Path) -> RepositoryVisibility:
    """Check if a repository is public or private.

    Uses GitHub CLI (gh) to determine repository visibility.
    Only works for GitHub repositories.

    Args:
        repo_path: Path to the Git repository

    Returns:
        RepositoryVisibility indicating public, private, or unknown
    """
    # Get remote URL
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return RepositoryVisibility.UNKNOWN
        remote_url = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return RepositoryVisibility.UNKNOWN

    # Check if it's a GitHub repository
    if not _is_github_url(remote_url):
        return RepositoryVisibility.UNKNOWN

    # Use gh CLI to check visibility
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "isPrivate", "--jq", ".isPrivate"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return RepositoryVisibility.UNKNOWN

        is_private = result.stdout.strip().lower() == "true"
        return RepositoryVisibility.PRIVATE if is_private else RepositoryVisibility.PUBLIC

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return RepositoryVisibility.UNKNOWN


def _is_github_url(url: str) -> bool:
    """Check if a URL is a GitHub repository URL."""
    patterns = [
        r"github\.com[:/]",  # Matches github.com: (SSH) or github.com/ (HTTPS)
    ]
    return any(re.search(pattern, url) for pattern in patterns)


@dataclass
class ProjectSession:
    """A session with project metadata."""

    session_id: str
    project_name: str
    project_path: Path
    branch: str | None
    messages: list[Message]


def discover_sessions(
    claude_projects_path: Path | None = None,
    since: datetime | None = None,
) -> Iterator[tuple[Path, str, Path]]:
    """Discover all session files.

    Args:
        claude_projects_path: Path to Claude Code projects directory.
        since: If provided, only yield files modified after this timestamp.

    Yields:
        Tuples of (session_file_path, session_id, project_path)
    """
    projects_path = claude_projects_path or get_claude_projects_path()

    if not projects_path.exists():
        return

    for project_dir in projects_path.iterdir():
        if not project_dir.is_dir():
            continue

        project_path = decode_project_path(project_dir.name)

        for session_file in project_dir.glob("*.jsonl"):
            # Filter by modification time if since is provided
            if since is not None:
                mtime = datetime.fromtimestamp(
                    session_file.stat().st_mtime, tz=since.tzinfo
                )
                if mtime <= since:
                    continue

            session_id = session_file.stem
            yield session_file, session_id, project_path


def collect_sessions(
    config: Config,
    date_filter: datetime | None = None,
    since: datetime | None = None,
) -> list[ProjectSession]:
    """Collect all sessions with their messages.

    Args:
        config: Application configuration
        date_filter: If provided, only include messages from this date
        since: If provided, only include sessions from files modified after this timestamp

    Returns:
        List of ProjectSession objects
    """
    sessions = []

    for session_file, session_id, project_path in discover_sessions(since=since):
        messages = list(
            parse_session_file(
                session_file,
                exclude_system=config.sync.exclude_system,
                exclude_tool_messages=config.sync.exclude_tool_messages,
                date_filter=date_filter,
            )
        )

        if not messages:
            continue

        # Get project name (use alias if defined)
        project_name = config.project_aliases.get(
            str(project_path),
            extract_project_name(project_path),
        )

        # Get branch info
        branch = get_git_branch(project_path) if project_path.exists() else None

        sessions.append(
            ProjectSession(
                session_id=session_id,
                project_name=project_name,
                project_path=project_path,
                branch=branch,
                messages=messages,
            )
        )

    return sessions


def format_message_markdown(msg: Message) -> str:
    """Format a message as Markdown."""
    timestamp_str = msg.timestamp.strftime("%H:%M:%S")
    role = "User" if msg.type == "user" else "Assistant"
    return f"### {timestamp_str} {role}\n\n{msg.content}\n"


def format_session_markdown(session: ProjectSession) -> str:
    """Format a session as Markdown."""
    if not session.messages:
        return ""

    start_ts = session.messages[0].timestamp
    end_ts = session.messages[-1].timestamp
    start_time = start_ts.strftime("%H:%M")
    end_time = end_ts.strftime("%H:%M")

    # Calculate day difference for sessions spanning multiple days
    day_diff = (end_ts.date() - start_ts.date()).days
    time_range = f"{start_time} - {end_time}"
    if day_diff > 0:
        time_range += f" (+{day_diff})"

    lines = [
        f"## Session: {session.session_id[:8]} ({time_range})",
    ]

    # Add metadata
    metadata = []
    if session.branch:
        metadata.append(f"**Branch:** {session.branch}")
    metadata.append(f"**Path:** {session.project_path}")
    if metadata:
        lines.append(" | ".join(metadata))

    lines.append("")

    # Add messages
    for msg in session.messages:
        lines.append(format_message_markdown(msg))

    lines.append("---\n")

    return "\n".join(lines)


def generate_output_path(
    config: Config,
    project_name: str,
    date: datetime,
) -> Path:
    """Generate the output file path based on configuration.

    Args:
        config: Application configuration
        project_name: Name of the project
        date: Date of the log

    Returns:
        Path to the output file
    """
    repo_path = config.output.repository

    # Sanitize project name for filesystem
    safe_project_name = project_name.replace("/", "-").replace("\\", "-")

    if config.output.structure == "date":
        # Date-based: YYYY/MM/DD/project-name.md
        return (
            repo_path
            / str(date.year)
            / f"{date.month:02d}"
            / f"{date.day:02d}"
            / f"{safe_project_name}.md"
        )
    else:
        # Project-based: project-name/YYYY-MM-DD.md
        return repo_path / safe_project_name / f"{date.strftime('%Y-%m-%d')}.md"


def write_markdown_file(
    path: Path,
    project_name: str,
    date: datetime,
    sessions: list[ProjectSession],
) -> None:
    """Write sessions to a Markdown file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    date_str = date.strftime("%Y-%m-%d")
    lines = [f"# {project_name} - {date_str}\n\n"]

    # Sort sessions by start time
    sorted_sessions = sorted(
        sessions,
        key=lambda s: s.messages[0].timestamp if s.messages else datetime.min,
    )

    for session in sorted_sessions:
        lines.append(format_session_markdown(session))

    path.write_text("".join(lines))


def sync_logs(
    config: Config,
    date_filter: datetime | None = None,
    dry_run: bool = False,
    since: datetime | None = None,
) -> list[Path]:
    """Sync conversation logs to the output repository.

    Args:
        config: Application configuration
        date_filter: If provided, only sync logs from this date
        dry_run: If True, don't actually write files
        since: If provided, only sync files modified after this timestamp

    Returns:
        List of paths that were written (or would be written in dry run)
    """
    sessions = collect_sessions(config, date_filter, since=since)

    if not sessions:
        return []

    # Group sessions by (project_name, date)
    grouped: dict[tuple[str, datetime], list[ProjectSession]] = defaultdict(list)
    for session in sessions:
        if session.messages:
            date = session.messages[0].timestamp.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            grouped[(session.project_name, date)].append(session)

    written_paths = []
    for (project_name, date), project_sessions in grouped.items():
        output_path = generate_output_path(config, project_name, date)

        if not dry_run:
            write_markdown_file(output_path, project_name, date, project_sessions)

        written_paths.append(output_path)

    return written_paths


def git_commit_and_push(
    repo_path: Path,
    remote: str = "origin",
    branch: str = "main",
    auto_push: bool = True,
) -> bool:
    """Commit changes and optionally push to remote.

    Args:
        repo_path: Path to the Git repository
        remote: Remote name
        branch: Branch name
        auto_push: Whether to push to remote

    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if there are changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if not result.stdout.strip():
            return True  # No changes to commit

        # Add all changes
        subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_path,
            check=True,
            timeout=10,
        )

        # Commit
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subprocess.run(
            ["git", "commit", "-m", f"Update conversation logs ({timestamp})"],
            cwd=repo_path,
            check=True,
            timeout=30,
        )

        # Push
        if auto_push:
            subprocess.run(
                ["git", "push", remote, branch],
                cwd=repo_path,
                check=True,
                timeout=60,
            )

        return True

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
