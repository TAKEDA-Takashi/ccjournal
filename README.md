# ccjournal

Sync Claude Code conversation logs to a Git repository.

## Features

- Automatically sync Claude Code session logs to a Git repository
- Organize logs by date or project
- Support for worktrees (groups by Git remote URL)
- Auto-commit and push to remote
- Configurable via TOML

## Installation

```bash
pipx install ccjournal
# or
uv tool install ccjournal
```

## Quick Start

```bash
# Initialize configuration
ccjournal init

# Manually sync logs
ccjournal sync

# Show configuration
ccjournal config show
```

## Configuration

Configuration file is located at `~/.config/ccjournal/config.toml`:

```toml
[output]
repository = "~/Documents/claude-logs"
structure = "date"    # "date" or "project"
remote = "origin"
branch = "main"
auto_push = true

[sync]
interval = 300        # seconds (for daemon)
exclude_system = true # exclude system messages
```

### Directory Structure

**Date-based (default):**
```
claude-logs/
└── 2026/01/16/
    ├── my-project.md
    └── another-repo.md
```

**Project-based:**
```
claude-logs/
└── github.com-user-my-project/
    ├── 2026-01-16.md
    └── 2026-01-15.md
```

## Commands

| Command | Description |
|---------|-------------|
| `ccjournal init` | Initialize configuration interactively |
| `ccjournal sync` | Sync logs to repository |
| `ccjournal sync --dry-run` | Preview what would be synced |
| `ccjournal sync --date 2026-01-16` | Sync specific date |
| `ccjournal config show` | Show current configuration |
| `ccjournal config edit` | Open config in editor |
| `ccjournal list` | List recent synced logs |
| `ccjournal daemon install` | Show daemon setup instructions |

## Automatic Sync

### macOS (launchd)

```bash
ccjournal daemon install
```

Follow the instructions to set up automatic sync every 5 minutes.

### Linux (systemd)

Create user services for periodic sync. See `ccjournal daemon install` for details.

### cron

```bash
# Sync every 5 minutes
*/5 * * * * /usr/local/bin/ccjournal sync
```

## Development

```bash
# Clone the repository
git clone https://github.com/TAKEDA-Takashi/ccjournal.git
cd ccjournal

# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Type check
uv run pyright

# Lint
uv run ruff check
```

## License

MIT
