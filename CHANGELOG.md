# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-01-23

### Fixed

- LaunchAgent に PATH 環境変数を追加し、Homebrew でインストールした `gh` CLI が見つからない問題を修正
  - Apple Silicon (`/opt/homebrew/bin`) と Intel Mac (`/usr/local/bin`) の両方に対応
  - repository visibility チェックが正常に動作するようになった

## [0.2.0] - 2025-01-19

### Added

- `daemon uninstall` command to remove installed service (launchd/systemd)
- Troubleshooting section in README for macOS "unidentified developer" warning

### Changed

- Sessions spanning multiple days are now split by message timestamp into separate daily files
  - Previously: All messages saved to the session start date's file
  - Now: Each message is saved to its respective date's file

## [0.1.0] - 2025-01-18

### Added

- Initial release
- Sync Claude Code session logs to Git repository
- Output structure options: date-based (`YYYY/MM/DD/project.md`) or project-based (`project/YYYY-MM-DD.md`)
- Worktree support (groups logs by Git remote URL)
- Auto-commit and push to remote
- TOML configuration (`~/.config/ccjournal/config.toml`)
- Daemon mode with periodic sync
- Incremental sync (only sync modified files)
- Security features:
  - Public repository protection (blocks push by default)
  - Unknown visibility protection
  - Sensitive data masking (API keys, tokens, passwords)
- Platform support:
  - macOS (launchd)
  - Linux (systemd)
- CLI commands:
  - `init` - Interactive configuration setup
  - `sync` - Manual log sync with `--dry-run`, `--date`, `--no-commit`, `--no-push` options
  - `config show/edit` - Configuration management
  - `list` - List recent synced logs
  - `daemon start/stop/status/install` - Daemon management
