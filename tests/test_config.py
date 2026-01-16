"""Tests for the config module."""

from pathlib import Path

from ccjournal.config import Config


class TestConfig:
    """Tests for Config class."""

    def test_default_config(self) -> None:
        """Default config should have sensible defaults."""
        config = Config()

        assert config.output.structure == "date"
        assert config.output.auto_push is True
        assert config.output.remote == "origin"
        assert config.output.branch == "main"
        assert config.sync.interval == 300
        assert config.sync.exclude_system is True

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Loading nonexistent file should return defaults."""
        config = Config.load(tmp_path / "nonexistent.toml")

        assert config.output.structure == "date"

    def test_load_and_save_config(self, tmp_path: Path) -> None:
        """Config should be loadable after saving."""
        config_path = tmp_path / "config.toml"

        # Create and save config
        config = Config()
        config.output.repository = tmp_path / "logs"
        config.output.structure = "project"
        config.output.auto_push = False
        config.sync.interval = 600

        config.save(config_path)

        # Load it back
        loaded = Config.load(config_path)

        assert loaded.output.repository == tmp_path / "logs"
        assert loaded.output.structure == "project"
        assert loaded.output.auto_push is False
        assert loaded.sync.interval == 600

    def test_load_with_aliases(self, tmp_path: Path) -> None:
        """Config should load project aliases."""
        config_path = tmp_path / "config.toml"
        config_path.write_text('''
[output]
repository = "~/logs"
structure = "date"

[projects.aliases]
"/path/to/project" = "my-alias"
''')

        config = Config.load(config_path)
        assert config.output.structure == "date"
