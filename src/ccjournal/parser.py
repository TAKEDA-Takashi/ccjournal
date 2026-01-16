"""Parser for Claude Code session files."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Message:
    """A single message in a conversation."""

    type: str  # "user" or "assistant"
    timestamp: datetime
    content: str


@dataclass
class Session:
    """A conversation session."""

    session_id: str
    project_path: Path
    messages: list[Message]

    @property
    def start_time(self) -> datetime | None:
        """Get the start time of the session."""
        if not self.messages:
            return None
        return self.messages[0].timestamp

    @property
    def end_time(self) -> datetime | None:
        """Get the end time of the session."""
        if not self.messages:
            return None
        return self.messages[-1].timestamp


def decode_project_path(encoded: str) -> Path:
    """Decode a Claude Code project directory name to original path.

    Claude Code encodes paths by replacing '/' with '-'.
    Example: -Users-takeda-projects-myapp -> /Users/takeda/projects/myapp
    """
    if encoded.startswith("-"):
        # Remove leading '-' and replace remaining '-' with '/'
        path_str = "/" + encoded[1:].replace("-", "/")
    else:
        path_str = encoded.replace("-", "/")

    return Path(path_str)


def get_git_remote_url(path: Path) -> str | None:
    """Get the Git remote URL for a directory."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def get_git_branch(path: Path) -> str | None:
    """Get the current Git branch for a directory."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def normalize_remote_url(url: str) -> str:
    """Normalize a Git remote URL to a consistent format.

    Example:
        git@github.com:user/repo.git -> github.com/user/repo
        https://github.com/user/repo.git -> github.com/user/repo
    """
    # Remove .git suffix
    url = re.sub(r"\.git$", "", url)

    # Handle SSH URLs (git@github.com:user/repo)
    ssh_match = re.match(r"git@([^:]+):(.+)", url)
    if ssh_match:
        return f"{ssh_match.group(1)}/{ssh_match.group(2)}"

    # Handle HTTPS URLs (https://github.com/user/repo)
    https_match = re.match(r"https?://([^/]+)/(.+)", url)
    if https_match:
        return f"{https_match.group(1)}/{https_match.group(2)}"

    return url


def extract_project_name(path: Path) -> str:
    """Extract a project name from a path.

    Uses Git remote URL if available, otherwise uses directory name.
    """
    remote_url = get_git_remote_url(path)
    if remote_url:
        return normalize_remote_url(remote_url)
    return path.name


def extract_text_content(content: str | list | dict) -> str:
    """Extract text content from various message formats."""
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "tool_use":
                    tool_name = item.get("name", "unknown")
                    texts.append(f"[Tool: {tool_name}]")
                elif item.get("type") == "tool_result":
                    texts.append("[Tool Result]")
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts)

    # content is dict
    if content.get("type") == "text":
        return content.get("text", "")
    return str(content)


def is_system_message(content: str) -> bool:
    """Check if a message is a system message that should be excluded."""
    patterns = [
        r"<system-reminder>",
        r"<local-command-",
        r"</system-reminder>",
        r"</local-command-",
    ]
    return any(re.search(pattern, content) for pattern in patterns)


def parse_session_file(
    file_path: Path,
    exclude_system: bool = True,
    date_filter: datetime | None = None,
) -> Iterator[Message]:
    """Parse a Claude Code session file (.jsonl).

    Args:
        file_path: Path to the session file
        exclude_system: Whether to exclude system messages
        date_filter: If provided, only include messages from this date

    Yields:
        Message objects
    """
    with file_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            if msg_type not in ("user", "assistant"):
                continue

            timestamp_str = data.get("timestamp")
            if not timestamp_str:
                continue

            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                continue

            # Apply date filter
            if date_filter and timestamp.date() != date_filter.date():
                continue

            # Extract content
            message_data = data.get("message", {})
            content_raw = message_data.get("content", "")
            content = extract_text_content(content_raw)

            # Exclude system messages
            if exclude_system and is_system_message(content):
                continue

            if not content.strip():
                continue

            yield Message(type=msg_type, timestamp=timestamp, content=content)
