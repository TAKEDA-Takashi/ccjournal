"""Tests for the parser module."""

from datetime import UTC, datetime
from pathlib import Path

from ccjournal.parser import (
    decode_project_path,
    extract_text_content,
    is_system_message,
    normalize_remote_url,
    parse_session_file,
)


class TestDecodeProjectPath:
    """Tests for decode_project_path function."""

    def test_decode_absolute_path(self) -> None:
        """Absolute paths start with '-' which becomes '/'."""
        encoded = "-Users-takeda-projects-myapp"
        result = decode_project_path(encoded)
        assert result == Path("/Users/takeda/projects/myapp")

    def test_decode_relative_path(self) -> None:
        """Relative paths don't start with '-'."""
        encoded = "projects-myapp"
        result = decode_project_path(encoded)
        assert result == Path("projects/myapp")


class TestNormalizeRemoteUrl:
    """Tests for normalize_remote_url function."""

    def test_ssh_url(self) -> None:
        """SSH URLs should be normalized."""
        url = "git@github.com:user/repo.git"
        result = normalize_remote_url(url)
        assert result == "github.com/user/repo"

    def test_https_url(self) -> None:
        """HTTPS URLs should be normalized."""
        url = "https://github.com/user/repo.git"
        result = normalize_remote_url(url)
        assert result == "github.com/user/repo"

    def test_url_without_git_suffix(self) -> None:
        """URLs without .git suffix should work."""
        url = "https://github.com/user/repo"
        result = normalize_remote_url(url)
        assert result == "github.com/user/repo"


class TestExtractTextContent:
    """Tests for extract_text_content function."""

    def test_string_content(self) -> None:
        """String content should be returned as-is."""
        result = extract_text_content("Hello, world!")
        assert result == "Hello, world!"

    def test_list_with_text_items(self) -> None:
        """List with text items should be joined."""
        content = [
            {"type": "text", "text": "First line"},
            {"type": "text", "text": "Second line"},
        ]
        result = extract_text_content(content)
        assert result == "First line\nSecond line"

    def test_list_with_tool_use(self) -> None:
        """Tool use items should show tool name."""
        content = [
            {"type": "text", "text": "Let me check"},
            {"type": "tool_use", "name": "read_file"},
        ]
        result = extract_text_content(content)
        assert "Let me check" in result
        assert "[Tool: read_file]" in result

    def test_dict_with_text_type(self) -> None:
        """Dict with type=text should return the text."""
        content = {"type": "text", "text": "Hello"}
        result = extract_text_content(content)
        assert result == "Hello"


class TestIsSystemMessage:
    """Tests for is_system_message function."""

    def test_system_reminder_tag(self) -> None:
        """Messages with system-reminder tags should be detected."""
        content = "<system-reminder>Some system info</system-reminder>"
        assert is_system_message(content) is True

    def test_local_command_tag(self) -> None:
        """Messages with local-command tags should be detected."""
        content = "<local-command-output>output</local-command-output>"
        assert is_system_message(content) is True

    def test_normal_message(self) -> None:
        """Normal messages should not be flagged."""
        content = "Please help me fix this bug"
        assert is_system_message(content) is False


class TestParseSessionFile:
    """Tests for parse_session_file function."""

    def test_parse_valid_session(self, tmp_path: Path) -> None:
        """Parse a valid session file."""
        session_file = tmp_path / "session.jsonl"
        lines = [
            '{"type": "user", "timestamp": "2024-01-15T10:30:00Z", '
            '"message": {"content": "Hello"}}',
            '{"type": "assistant", "timestamp": "2024-01-15T10:30:15Z", '
            '"message": {"content": "Hi there!"}}',
        ]
        session_file.write_text("\n".join(lines) + "\n")

        messages = list(parse_session_file(session_file))

        assert len(messages) == 2
        assert messages[0].type == "user"
        assert messages[0].content == "Hello"
        assert messages[1].type == "assistant"
        assert messages[1].content == "Hi there!"

    def test_parse_with_date_filter(self, tmp_path: Path) -> None:
        """Parse with date filter should only return matching messages."""
        session_file = tmp_path / "session.jsonl"
        lines = [
            '{"type": "user", "timestamp": "2024-01-15T10:30:00Z", '
            '"message": {"content": "Day 1"}}',
            '{"type": "user", "timestamp": "2024-01-16T10:30:00Z", '
            '"message": {"content": "Day 2"}}',
        ]
        session_file.write_text("\n".join(lines) + "\n")

        date_filter = datetime(2024, 1, 15, tzinfo=UTC)
        messages = list(parse_session_file(session_file, date_filter=date_filter))

        assert len(messages) == 1
        assert messages[0].content == "Day 1"

    def test_exclude_system_messages(self, tmp_path: Path) -> None:
        """System messages should be excluded by default."""
        session_file = tmp_path / "session.jsonl"
        system_content = "<system-reminder>test</system-reminder>"
        lines = [
            '{"type": "user", "timestamp": "2024-01-15T10:30:00Z", '
            '"message": {"content": "Hello"}}',
            '{"type": "assistant", "timestamp": "2024-01-15T10:30:15Z", '
            f'"message": {{"content": "{system_content}"}}}}',
        ]
        session_file.write_text("\n".join(lines) + "\n")

        messages = list(parse_session_file(session_file, exclude_system=True))

        assert len(messages) == 1
        assert messages[0].content == "Hello"

    def test_include_system_messages(self, tmp_path: Path) -> None:
        """System messages should be included when exclude_system=False."""
        session_file = tmp_path / "session.jsonl"
        system_content = "<system-reminder>test</system-reminder>"
        lines = [
            '{"type": "user", "timestamp": "2024-01-15T10:30:00Z", '
            '"message": {"content": "Hello"}}',
            '{"type": "assistant", "timestamp": "2024-01-15T10:30:15Z", '
            f'"message": {{"content": "{system_content}"}}}}',
        ]
        session_file.write_text("\n".join(lines) + "\n")

        messages = list(parse_session_file(session_file, exclude_system=False))

        assert len(messages) == 2
