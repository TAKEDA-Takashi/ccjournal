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

    Claude Code encodes paths by replacing '/' and '.' with '-'.
    This function attempts to find the correct path by checking
    for directory existence at each step.

    Example:
        -Users-takeda-takashi-ghq-github-com-org-repo
        -> /Users/takeda.takashi/ghq/github.com/org/repo (if these dirs exist)
    """
    if not encoded.startswith("-"):
        # Relative path - simple replacement
        return Path(encoded.replace("-", "/"))

    parts = encoded[1:].split("-")
    return _find_existing_path(parts, Path("/"))


def _find_existing_path(parts: list[str], base: Path) -> Path:
    """Find the actual path by checking directory existence.

    Tries to reconstruct the original path by checking if directories exist.
    When a directory doesn't exist with '/' separator, tries '.' then '-'.
    """
    if not parts:
        return base

    result_parts: list[str] = []
    i = 0

    while i < len(parts):
        segment = parts[i]

        # Try to find the longest matching segment
        best_match = segment
        best_match_end = i + 1

        j = i + 1
        while j < len(parts):
            # Try extending with '.' or '-'
            test_with_dot = segment + "." + parts[j]
            test_with_dash = segment + "-" + parts[j]

            test_path_dot = base / "/".join(result_parts + [test_with_dot])
            test_path_dash = base / "/".join(result_parts + [test_with_dash])

            if test_path_dot.exists() and test_path_dot.is_dir():
                segment = test_with_dot
                best_match = segment
                best_match_end = j + 1
                j += 1
            elif test_path_dash.exists() and test_path_dash.is_dir():
                segment = test_with_dash
                best_match = segment
                best_match_end = j + 1
                j += 1
            else:
                # No match found with extended segment
                break

        result_parts.append(best_match)
        i = best_match_end

    return base / "/".join(result_parts)


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
        ssh://git@github.com/user/repo.git -> github.com/user/repo
    """
    # Remove .git suffix
    url = re.sub(r"\.git$", "", url)

    # Handle SSH URLs in scp-like syntax (git@github.com:user/repo)
    scp_match = re.match(r"git@([^:]+):(.+)", url)
    if scp_match:
        return f"{scp_match.group(1)}/{scp_match.group(2)}"

    # Handle SSH URLs in URL syntax (ssh://git@github.com/user/repo)
    ssh_url_match = re.match(r"ssh://git@([^/]+)/(.+)", url)
    if ssh_url_match:
        return f"{ssh_url_match.group(1)}/{ssh_url_match.group(2)}"

    # Handle HTTPS URLs (https://github.com/user/repo)
    https_match = re.match(r"https?://([^/]+)/(.+)", url)
    if https_match:
        return f"{https_match.group(1)}/{https_match.group(2)}"

    return url


def extract_project_name(path: Path) -> str:
    """Extract a project name from a path.

    Uses Git remote URL if available, otherwise uses directory name with '_local-' prefix.
    """
    remote_url = get_git_remote_url(path)
    if remote_url:
        return normalize_remote_url(remote_url)
    return f"_local-{path.name}"


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
