"""Tests for the sync module."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from ccjournal.config import Config
from ccjournal.parser import Message
from ccjournal.sync import (
    ProjectSession,
    PublicRepositoryError,
    RepositoryVisibility,
    check_repository_visibility,
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

    def test_format_session_spanning_days(self) -> None:
        """Session spanning multiple days should show (+N) indicator."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch="main",
            messages=[
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 15, 22, 30, 0, tzinfo=UTC),
                    content="Starting late",
                ),
                Message(
                    type="assistant",
                    timestamp=datetime(2024, 1, 16, 2, 45, 0, tzinfo=UTC),
                    content="Still working",
                ),
            ],
        )

        result = format_session_markdown(session)

        assert "22:30 - 02:45 (+1)" in result

    def test_format_session_spanning_multiple_days(self) -> None:
        """Session spanning multiple days should show (+N) indicator."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch="main",
            messages=[
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                    content="Day 1",
                ),
                Message(
                    type="assistant",
                    timestamp=datetime(2024, 1, 17, 15, 45, 0, tzinfo=UTC),
                    content="Day 3",
                ),
            ],
        )

        result = format_session_markdown(session)

        assert "10:30 - 15:45 (+2)" in result


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


class TestCheckRepositoryVisibility:
    """Tests for check_repository_visibility function."""

    def test_private_repository(self, tmp_path: Path) -> None:
        """Private GitHub repository should return PRIVATE."""
        with patch("ccjournal.sync.subprocess.run") as mock_run:
            mock_remote = type(
                "Result", (), {"returncode": 0, "stdout": "git@github.com:user/repo.git\n"}
            )()
            mock_gh = type("Result", (), {"returncode": 0, "stdout": "true\n"})()
            mock_run.side_effect = [mock_remote, mock_gh]

            result = check_repository_visibility(tmp_path)

            assert result == RepositoryVisibility.PRIVATE

    def test_public_repository(self, tmp_path: Path) -> None:
        """Public GitHub repository should return PUBLIC."""
        with patch("ccjournal.sync.subprocess.run") as mock_run:
            mock_remote = type(
                "Result", (), {"returncode": 0, "stdout": "https://github.com/user/repo.git\n"}
            )()
            mock_gh = type("Result", (), {"returncode": 0, "stdout": "false\n"})()
            mock_run.side_effect = [mock_remote, mock_gh]

            result = check_repository_visibility(tmp_path)

            assert result == RepositoryVisibility.PUBLIC

    def test_non_github_repository(self, tmp_path: Path) -> None:
        """Non-GitHub repository should return UNKNOWN."""
        with patch("ccjournal.sync.subprocess.run") as mock_run:
            mock_remote = type(
                "Result", (), {"returncode": 0, "stdout": "git@gitlab.com:user/repo.git\n"}
            )()
            mock_run.return_value = mock_remote

            result = check_repository_visibility(tmp_path)

            assert result == RepositoryVisibility.UNKNOWN

    def test_no_remote(self, tmp_path: Path) -> None:
        """Repository without remote should return UNKNOWN."""
        with patch("ccjournal.sync.subprocess.run") as mock_run:
            mock_run.return_value = type("Result", (), {"returncode": 1, "stdout": ""})()

            result = check_repository_visibility(tmp_path)

            assert result == RepositoryVisibility.UNKNOWN

    def test_gh_command_fails(self, tmp_path: Path) -> None:
        """If gh command fails, should return UNKNOWN."""
        with patch("ccjournal.sync.subprocess.run") as mock_run:
            mock_remote = type(
                "Result", (), {"returncode": 0, "stdout": "git@github.com:user/repo.git\n"}
            )()
            mock_gh = type("Result", (), {"returncode": 1, "stdout": ""})()
            mock_run.side_effect = [mock_remote, mock_gh]

            result = check_repository_visibility(tmp_path)

            assert result == RepositoryVisibility.UNKNOWN


class TestPublicRepositoryError:
    """Tests for PublicRepositoryError."""

    def test_error_message(self) -> None:
        """Error message should include repository path and setting instructions."""
        error = PublicRepositoryError(Path("/path/to/repo"))

        message = str(error)

        assert "/path/to/repo" in message
        assert "allow_public_repository" in message
