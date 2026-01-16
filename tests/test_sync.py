"""Tests for the sync module."""

from datetime import UTC, datetime
from pathlib import Path

from ccjournal.config import Config
from ccjournal.parser import Message
from ccjournal.sync import (
    ProjectSession,
    format_message_markdown,
    format_session_markdown,
    generate_output_path,
    write_markdown_file,
)


class TestFormatMessageMarkdown:
    """Tests for format_message_markdown function."""

    def test_format_user_message(self) -> None:
        """User messages should be formatted correctly."""
        msg = Message(
            type="user",
            timestamp=datetime(2024, 1, 15, 10, 30, 15, tzinfo=UTC),
            content="Hello, world!",
        )

        result = format_message_markdown(msg)

        assert "### 10:30:15 User" in result
        assert "Hello, world!" in result

    def test_format_assistant_message(self) -> None:
        """Assistant messages should be formatted correctly."""
        msg = Message(
            type="assistant",
            timestamp=datetime(2024, 1, 15, 10, 31, 0, tzinfo=UTC),
            content="Hi there!",
        )

        result = format_message_markdown(msg)

        assert "### 10:31:00 Assistant" in result
        assert "Hi there!" in result


class TestFormatSessionMarkdown:
    """Tests for format_session_markdown function."""

    def test_format_session(self) -> None:
        """Session should be formatted with header and messages."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch="main",
            messages=[
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                    content="Hello",
                ),
                Message(
                    type="assistant",
                    timestamp=datetime(2024, 1, 15, 10, 45, 0, tzinfo=UTC),
                    content="Hi",
                ),
            ],
        )

        result = format_session_markdown(session)

        assert "## Session: abc12345" in result
        assert "10:30 - 10:45" in result
        assert "**Branch:** main" in result
        assert "Hello" in result
        assert "Hi" in result

    def test_empty_session(self) -> None:
        """Empty session should return empty string."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch=None,
            messages=[],
        )

        result = format_session_markdown(session)

        assert result == ""


class TestGenerateOutputPath:
    """Tests for generate_output_path function."""

    def test_date_structure(self, tmp_path: Path) -> None:
        """Date structure should create YYYY/MM/DD/project.md path."""
        config = Config()
        config.output.repository = tmp_path
        config.output.structure = "date"

        date = datetime(2024, 1, 15)
        result = generate_output_path(config, "my-project", date)

        assert result == tmp_path / "2024" / "01" / "15" / "my-project.md"

    def test_project_structure(self, tmp_path: Path) -> None:
        """Project structure should create project/YYYY-MM-DD.md path."""
        config = Config()
        config.output.repository = tmp_path
        config.output.structure = "project"

        date = datetime(2024, 1, 15)
        result = generate_output_path(config, "my-project", date)

        assert result == tmp_path / "my-project" / "2024-01-15.md"

    def test_sanitize_project_name(self, tmp_path: Path) -> None:
        """Project names with slashes should be sanitized."""
        config = Config()
        config.output.repository = tmp_path
        config.output.structure = "date"

        date = datetime(2024, 1, 15)
        result = generate_output_path(config, "github.com/user/repo", date)

        assert "github.com-user-repo.md" in str(result)


class TestWriteMarkdownFile:
    """Tests for write_markdown_file function."""

    def test_write_file(self, tmp_path: Path) -> None:
        """Should write markdown file with proper content."""
        output_path = tmp_path / "2024" / "01" / "15" / "project.md"

        sessions = [
            ProjectSession(
                session_id="abc12345",
                project_name="my-project",
                project_path=Path("/path/to/project"),
                branch="main",
                messages=[
                    Message(
                        type="user",
                        timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                        content="Hello",
                    ),
                ],
            ),
        ]

        write_markdown_file(
            output_path,
            "my-project",
            datetime(2024, 1, 15),
            sessions,
        )

        assert output_path.exists()
        content = output_path.read_text()
        assert "# my-project - 2024-01-15" in content
        assert "Hello" in content
