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
    check_push_permission,
    check_repository_visibility,
    format_message_markdown,
    format_session_markdown,
    generate_output_path,
    split_session_by_date,
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


class TestCheckPushPermission:
    """Tests for check_push_permission function."""

    def test_private_repository_allowed(self, tmp_path: Path) -> None:
        """Private repositories should always be allowed."""
        with patch(
            "ccjournal.sync.check_repository_visibility",
            return_value=RepositoryVisibility.PRIVATE,
        ):
            result = check_push_permission(
                tmp_path, allow_public=False, allow_unknown=False
            )

            assert result.allowed is True
            assert result.visibility == RepositoryVisibility.PRIVATE
            assert result.warning_message is None

    def test_public_repository_blocked_by_default(self, tmp_path: Path) -> None:
        """Public repositories should be blocked when allow_public=False."""
        with patch(
            "ccjournal.sync.check_repository_visibility",
            return_value=RepositoryVisibility.PUBLIC,
        ):
            result = check_push_permission(
                tmp_path, allow_public=False, allow_unknown=False
            )

            assert result.allowed is False
            assert result.visibility == RepositoryVisibility.PUBLIC
            assert result.warning_message is not None
            assert "public repository" in result.warning_message.lower()

    def test_public_repository_allowed_when_permitted(self, tmp_path: Path) -> None:
        """Public repositories should be allowed when allow_public=True."""
        with patch(
            "ccjournal.sync.check_repository_visibility",
            return_value=RepositoryVisibility.PUBLIC,
        ):
            result = check_push_permission(
                tmp_path, allow_public=True, allow_unknown=False
            )

            assert result.allowed is True
            assert result.visibility == RepositoryVisibility.PUBLIC
            assert result.warning_message is not None  # Warning still shown

    def test_unknown_visibility_blocked_by_default(self, tmp_path: Path) -> None:
        """Unknown visibility should be blocked when allow_unknown=False."""
        with patch(
            "ccjournal.sync.check_repository_visibility",
            return_value=RepositoryVisibility.UNKNOWN,
        ):
            result = check_push_permission(
                tmp_path, allow_public=False, allow_unknown=False
            )

            assert result.allowed is False
            assert result.visibility == RepositoryVisibility.UNKNOWN
            assert result.warning_message is not None
            assert "unknown" in result.warning_message.lower()

    def test_unknown_visibility_allowed_when_permitted(self, tmp_path: Path) -> None:
        """Unknown visibility should be allowed when allow_unknown=True."""
        with patch(
            "ccjournal.sync.check_repository_visibility",
            return_value=RepositoryVisibility.UNKNOWN,
        ):
            result = check_push_permission(
                tmp_path, allow_public=False, allow_unknown=True
            )

            assert result.allowed is True
            assert result.visibility == RepositoryVisibility.UNKNOWN
            assert result.warning_message is not None  # Warning still shown


class TestSplitSessionByDate:
    """Tests for split_session_by_date function."""

    def test_single_day_session(self) -> None:
        """Session within a single day should not be split."""
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

        result = split_session_by_date(session)

        assert len(result) == 1
        date_key = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
        assert date_key in result
        assert len(result[date_key].messages) == 2

    def test_session_spanning_two_days(self) -> None:
        """Session spanning two days should be split by date."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch="main",
            messages=[
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 15, 23, 30, 0, tzinfo=UTC),
                    content="Day 1 message",
                ),
                Message(
                    type="assistant",
                    timestamp=datetime(2024, 1, 15, 23, 45, 0, tzinfo=UTC),
                    content="Day 1 response",
                ),
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 16, 0, 15, 0, tzinfo=UTC),
                    content="Day 2 message",
                ),
                Message(
                    type="assistant",
                    timestamp=datetime(2024, 1, 16, 0, 30, 0, tzinfo=UTC),
                    content="Day 2 response",
                ),
            ],
        )

        result = split_session_by_date(session)

        assert len(result) == 2

        day1 = datetime(2024, 1, 15, 0, 0, 0, tzinfo=UTC)
        day2 = datetime(2024, 1, 16, 0, 0, 0, tzinfo=UTC)

        assert day1 in result
        assert day2 in result

        assert len(result[day1].messages) == 2
        assert result[day1].messages[0].content == "Day 1 message"
        assert result[day1].messages[1].content == "Day 1 response"

        assert len(result[day2].messages) == 2
        assert result[day2].messages[0].content == "Day 2 message"
        assert result[day2].messages[1].content == "Day 2 response"

    def test_session_spanning_multiple_days(self) -> None:
        """Session spanning multiple days should create separate entries."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch="main",
            messages=[
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC),
                    content="Day 1",
                ),
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 16, 10, 0, 0, tzinfo=UTC),
                    content="Day 2",
                ),
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 17, 10, 0, 0, tzinfo=UTC),
                    content="Day 3",
                ),
            ],
        )

        result = split_session_by_date(session)

        assert len(result) == 3

    def test_split_preserves_session_metadata(self) -> None:
        """Split sessions should preserve original session metadata."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch="feature-branch",
            messages=[
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 15, 23, 30, 0, tzinfo=UTC),
                    content="Day 1",
                ),
                Message(
                    type="user",
                    timestamp=datetime(2024, 1, 16, 0, 30, 0, tzinfo=UTC),
                    content="Day 2",
                ),
            ],
        )

        result = split_session_by_date(session)

        for split_session in result.values():
            assert split_session.session_id == "abc12345"
            assert split_session.project_name == "my-project"
            assert split_session.project_path == Path("/path/to/project")
            assert split_session.branch == "feature-branch"

    def test_empty_session(self) -> None:
        """Empty session should return empty dict."""
        session = ProjectSession(
            session_id="abc12345",
            project_name="my-project",
            project_path=Path("/path/to/project"),
            branch=None,
            messages=[],
        )

        result = split_session_by_date(session)

        assert len(result) == 0
