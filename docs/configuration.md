# Configuration Reference

Complete configuration reference for ccjournal.

## Configuration File Location

```
~/.config/ccjournal/config.toml
```

## Creating the Configuration File

```bash
# Create interactively
ccjournal init

# Or create manually
mkdir -p ~/.config/ccjournal
touch ~/.config/ccjournal/config.toml
```

## Complete Configuration Example

```toml
[output]
repository = "~/Documents/claude-logs"
structure = "date"
remote = "origin"
branch = "main"
auto_push = true
allow_public_repository = false
allow_unknown_visibility = false

[sync]
interval = 300
exclude_system = true
exclude_tool_messages = true

[projects.aliases]
"/path/to/project" = "custom-name"
```

---

## [output] Section

Settings for output destination and Git operations.

### repository

| Property | Value |
|----------|-------|
| Type | Path (string) |
| Default | `~/Documents/claude-logs` |
| Required | No |

Path to the Git repository where logs are output. Supports `~` (home directory) expansion.

```toml
repository = "~/Documents/claude-logs"
```

### structure

| Property | Value |
|----------|-------|
| Type | `"date"` or `"project"` |
| Default | `"date"` |
| Required | No |

Directory structure for log files.

**`"date"` (date-based)**
```
claude-logs/
└── 2026/
    └── 01/
        └── 17/
            ├── github.com-user-project-a.md
            └── github.com-user-project-b.md
```

**`"project"` (project-based)**
```
claude-logs/
├── github.com-user-project-a/
│   ├── 2026-01-16.md
│   └── 2026-01-17.md
└── github.com-user-project-b/
    └── 2026-01-17.md
```

### remote

| Property | Value |
|----------|-------|
| Type | String |
| Default | `"origin"` |
| Required | No |

Git remote name for pushing.

```toml
remote = "origin"
```

### branch

| Property | Value |
|----------|-------|
| Type | String |
| Default | `"main"` |
| Required | No |

Git branch name for pushing.

```toml
branch = "main"
```

### auto_push

| Property | Value |
|----------|-------|
| Type | Boolean |
| Default | `true` |
| Required | No |

Whether to automatically push to remote after committing.

```toml
auto_push = true   # Push after commit
auto_push = false  # Commit only (no push)
```

### allow_public_repository

| Property | Value |
|----------|-------|
| Type | Boolean |
| Default | `false` |
| Required | No |

**Security setting**: Whether to allow pushing to public repositories.

Session logs may contain sensitive information such as API keys or internal URLs, so pushing to public repositories is blocked by default.

```toml
allow_public_repository = false  # Block push to public repos (recommended)
allow_public_repository = true   # Allow push to public repos (use with caution)
```

> **Note**: Public repository detection requires GitHub CLI (`gh`).

### allow_unknown_visibility

| Property | Value |
|----------|-------|
| Type | Boolean |
| Default | `false` |
| Required | No |

**Security setting**: Whether to allow pushing when repository visibility cannot be determined.

Visibility becomes "unknown" in the following cases:
- Non-GitHub hosting services (GitLab, Bitbucket, etc.)
- GitHub CLI (`gh`) is not installed
- GitHub CLI is not authenticated

```toml
allow_unknown_visibility = false  # Block push when unknown (recommended)
allow_unknown_visibility = true   # Allow push when unknown
```

---

## [sync] Section

Settings for sync behavior.

### interval

| Property | Value |
|----------|-------|
| Type | Integer (seconds) |
| Default | `300` (5 minutes) |
| Required | No |

Sync interval in seconds for daemon mode.

```toml
interval = 300   # Every 5 minutes
interval = 3600  # Every hour
```

### exclude_system

| Property | Value |
|----------|-------|
| Type | Boolean |
| Default | `true` |
| Required | No |

Whether to exclude system messages (`<system-reminder>` tags, etc.) from output.

```toml
exclude_system = true   # Exclude system messages (recommended)
exclude_system = false  # Include system messages
```

### exclude_tool_messages

| Property | Value |
|----------|-------|
| Type | Boolean |
| Default | `true` |
| Required | No |

Whether to exclude tool-only messages (`[Tool: Read]`, etc.) from output.

```toml
exclude_tool_messages = true   # Exclude tool-only messages (recommended)
exclude_tool_messages = false  # Include all messages
```

---

## [projects.aliases] Section

Project path alias settings.

### Format

```toml
[projects.aliases]
"/full/path/to/project" = "alias-name"
```

### Example

```toml
[projects.aliases]
"/Users/user/work/my-long-project-name" = "my-project"
"/Users/user/ghq/github.com/org/repo" = "org-repo"
```

When an alias is set, the output filename uses the alias name:

```
# Without alias
claude-logs/2026/01/17/github.com-org-repo.md

# With alias ("short-name" configured)
claude-logs/2026/01/17/short-name.md
```

---

## Security Settings Summary

| Setting | Default | Recommended | Description |
|---------|---------|-------------|-------------|
| `allow_public_repository` | `false` | `false` | Allow push to public repos |
| `allow_unknown_visibility` | `false` | `false` | Allow push when visibility unknown |

### Recommended Settings (Private Use)

```toml
[output]
allow_public_repository = false
allow_unknown_visibility = false
```

### Using GitLab/Bitbucket

When using non-GitHub hosting services, automatic visibility detection is not available. The following setting is required:

```toml
[output]
allow_unknown_visibility = true  # Required
```

> **Warning**: Before enabling this setting, manually verify that the repository is private.

---

## Automatic Sensitive Data Masking

ccjournal automatically masks the following patterns:

- API keys (`sk-xxx`, `AKIA...`, etc.)
- GitHub tokens (`ghp_xxx`, `github_pat_xxx`)
- Bearer tokens
- Passwords (`password=xxx` pattern)
- Environment variable secrets

This serves as a fail-safe but does not guarantee complete removal of sensitive information. Avoid including sensitive information in session logs.

---

## Troubleshooting

### Configuration file not loaded

```bash
# Check configuration file location
ccjournal config show

# Check if configuration file exists
ls -la ~/.config/ccjournal/config.toml
```

### TOML syntax error

```bash
# Syntax check (using Python)
python3 -c "import tomllib; tomllib.load(open('$HOME/.config/ccjournal/config.toml', 'rb'))"
```

### Public repository error

```
Error: Refusing to push to public repository
```

Solutions:
1. Change the repository to private (recommended)
2. Set `allow_public_repository = true` (after understanding the risks)

### Unknown visibility error

```
Error: Repository visibility cannot be determined
```

Solutions:
1. Install and authenticate GitHub CLI
2. Set `allow_unknown_visibility = true` (after confirming the repository is private)
