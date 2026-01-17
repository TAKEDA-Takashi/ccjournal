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

    def test_decode_path_with_dots(self) -> None:
        """Paths with dots in directory names (e.g., github.com)."""
        import uuid

        # Use /tmp with unique subdirectory to avoid path encoding issues
        base = Path("/tmp") / f"ccjournal_test_{uuid.uuid4().hex[:8]}"
        try:
            (base / "ghq" / "github.com" / "user" / "repo").mkdir(parents=True)

            encoded = f"-tmp-{base.name}-ghq-github-com-user-repo"
            result = decode_project_path(encoded)
            assert result == base / "ghq" / "github.com" / "user" / "repo"
        finally:
            import shutil

            shutil.rmtree(base, ignore_errors=True)

    def test_decode_path_with_dashes(self) -> None:
        """Paths with dashes in directory names (e.g., my-project)."""
        import uuid

        base = Path("/tmp") / f"ccjournal_test_{uuid.uuid4().hex[:8]}"
        try:
            (base / "projects" / "my-project").mkdir(parents=True)

            encoded = f"-tmp-{base.name}-projects-my-project"
            result = decode_project_path(encoded)
            assert result == base / "projects" / "my-project"
        finally:
            import shutil

            shutil.rmtree(base, ignore_errors=True)

    def test_decode_path_with_dots_and_dashes(self) -> None:
        """Complex paths with both dots and dashes."""
        import uuid

        base = Path("/tmp") / f"ccjournal_test_{uuid.uuid4().hex[:8]}"
        try:
            (base / "ghq" / "github.com" / "org-name" / "my-repo").mkdir(parents=True)

            encoded = f"-tmp-{base.name}-ghq-github-com-org-name-my-repo"
            result = decode_project_path(encoded)
            assert result == base / "ghq" / "github.com" / "org-name" / "my-repo"
        finally:
            import shutil

            shutil.rmtree(base, ignore_errors=True)

    def test_decode_path_with_dotted_username(self) -> None:
        """Paths with dotted usernames (e.g., takeda.takashi)."""
        import uuid

        base = Path("/tmp") / f"ccjournal_test_{uuid.uuid4().hex[:8]}"
        try:
            (base / "Users" / "takeda.takashi" / "projects").mkdir(parents=True)

            encoded = f"-tmp-{base.name}-Users-takeda-takashi-projects"
            result = decode_project_path(encoded)
            assert result == base / "Users" / "takeda.takashi" / "projects"
        finally:
            import shutil

            shutil.rmtree(base, ignore_errors=True)

    def test_decode_relative_path(self) -> None:
        """Relative paths don't start with '-'."""
        # Relative paths use simple replacement (no existence check)
        encoded = "projects-myapp"
        result = decode_project_path(encoded)
        assert result == Path("projects/myapp")

    def test_decode_nonexistent_path(self) -> None:
        """Non-existent paths should use '/' as separator."""
        encoded = "-nonexistent-path-to-project"
        result = decode_project_path(encoded)
        # When path doesn't exist, uses simple '/' separation
        assert result == Path("/nonexistent/path/to/project")

    def test_decode_path_with_multiple_dashes(self) -> None:
        """Paths with multiple dashes in directory name (e.g., claude-code-journal)."""
        import uuid

        base = Path("/tmp") / f"ccjournal_test_{uuid.uuid4().hex[:8]}"
        try:
            (base / "ghq" / "github.com" / "user" / "claude-code-journal").mkdir(
                parents=True
            )

            encoded = f"-tmp-{base.name}-ghq-github-com-user-claude-code-journal"
            result = decode_project_path(encoded)
            assert result == base / "ghq" / "github.com" / "user" / "claude-code-journal"
        finally:
            import shutil

            shutil.rmtree(base, ignore_errors=True)


class TestNormalizeRemoteUrl:
    """Tests for normalize_remote_url function."""

    def test_ssh_scp_url(self) -> None:
        """SSH URLs in scp-like syntax should be normalized."""
        url = "git@github.com:user/repo.git"
        result = normalize_remote_url(url)
        assert result == "github.com/user/repo"

    def test_ssh_url_syntax(self) -> None:
        """SSH URLs in URL syntax should be normalized."""
        url = "ssh://git@github.com/user/repo.git"
        result = normalize_remote_url(url)
        assert result == "github.com/user/repo"

    def test_ssh_url_syntax_without_suffix(self) -> None:
        """SSH URLs in URL syntax without .git suffix should work."""
        url = "ssh://git@github.com/user/repo"
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
        """Messages with local-command tags should be cleaned by clean_content."""
        # local-command-output is handled by clean_content, not is_system_message
        from ccjournal.parser import clean_content

        content = "<local-command-output>output</local-command-output>"
        result = clean_content(content)
        assert result == ""  # Content is removed entirely

    def test_local_command_caveat_tag(self) -> None:
        """Messages with local-command-caveat tags should be detected."""
        content = "<local-command-caveat>Caveat: ...</local-command-caveat>"
        assert is_system_message(content) is True

    def test_normal_message(self) -> None:
        """Normal messages should not be flagged."""
        content = "Please help me fix this bug"
        assert is_system_message(content) is False


class TestIsToolOnlyMessage:
    """Tests for is_tool_only_message function."""

    def test_tool_use_only(self) -> None:
        """Messages with only [Tool: XXX] should be detected."""
        from ccjournal.parser import is_tool_only_message

        content = "[Tool: Read]"
        assert is_tool_only_message(content) is True

    def test_tool_result_only(self) -> None:
        """Messages with only [Tool Result] should be detected."""
        from ccjournal.parser import is_tool_only_message

        content = "[Tool Result]"
        assert is_tool_only_message(content) is True

    def test_multiple_tools(self) -> None:
        """Messages with multiple tools should be detected."""
        from ccjournal.parser import is_tool_only_message

        content = "[Tool: Read]\n[Tool: Glob]\n[Tool: Bash]"
        assert is_tool_only_message(content) is True

    def test_text_with_tool(self) -> None:
        """Messages with text and tools should NOT be detected."""
        from ccjournal.parser import is_tool_only_message

        content = "Let me check the file.\n[Tool: Read]"
        assert is_tool_only_message(content) is False

    def test_normal_message(self) -> None:
        """Normal messages should NOT be detected."""
        from ccjournal.parser import is_tool_only_message

        content = "This is a normal message"
        assert is_tool_only_message(content) is False


class TestCleanContent:
    """Tests for clean_content function."""

    def test_clean_command_tags(self) -> None:
        """Command tags should be cleaned."""
        from ccjournal.parser import clean_content

        content = "<command-name>/commit</command-name>"
        result = clean_content(content)
        assert result == "/commit"

    def test_clean_bash_tags(self) -> None:
        """Bash tags should be cleaned to readable format."""
        from ccjournal.parser import clean_content

        content = "<bash-input>git status</bash-input>"
        result = clean_content(content)
        assert "git status" in result

    def test_clean_mixed_content(self) -> None:
        """Mixed content with tags and text should be cleaned."""
        from ccjournal.parser import clean_content

        content = "Running: <bash-input>npm test</bash-input>\nResult: success"
        result = clean_content(content)
        assert "npm test" in result
        assert "Result: success" in result
        assert "<bash-input>" not in result

    def test_clean_preserves_normal_text(self) -> None:
        """Normal text without tags should be preserved."""
        from ccjournal.parser import clean_content

        content = "This is a normal message"
        result = clean_content(content)
        assert result == "This is a normal message"

    def test_clean_empty_tags(self) -> None:
        """Empty tags should be removed."""
        from ccjournal.parser import clean_content

        content = "<bash-stdout></bash-stdout><bash-stderr></bash-stderr>"
        result = clean_content(content)
        assert result.strip() == ""


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
