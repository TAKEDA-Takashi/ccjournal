"""CLI interface for ccjournal."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from . import __version__
from .config import (
    Config,
    get_default_config_path,
    get_last_sync,
    get_pid_file_path,
    save_last_sync,
)
from .daemon import (
    generate_launchd_plist,
    generate_systemd_service,
    get_daemon_status,
    get_default_log_path,
    get_launchd_plist_path,
    get_systemd_service_path,
    start_daemon,
    stop_daemon,
)
from .sync import (
    PublicRepositoryError,
    RepositoryVisibility,
    check_push_permission,
    git_commit_and_push,
    sync_logs,
)


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """ccjournal - Sync Claude Code conversation logs to Git repository."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load()


main = cli


@main.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Initialize ccjournal configuration interactively."""
    config_path = get_default_config_path()

    if config_path.exists() and not click.confirm(
        f"Config already exists at {config_path}. Overwrite?"
    ):
        click.echo("Aborted.")
        return

    click.echo("Setting up ccjournal configuration...\n")

    # Repository path
    default_repo = Path.home() / "Documents" / "claude-logs"
    repo_path = click.prompt(
        "Output repository path",
        default=str(default_repo),
        type=click.Path(),
    )

    # Structure
    structure = click.prompt(
        "Directory structure",
        default="date",
        type=click.Choice(["date", "project"]),
    )

    # Auto push
    auto_push = click.confirm("Auto-push to remote?", default=True)

    # Create config
    config = Config()
    config.output.repository = Path(repo_path).expanduser()
    config.output.structure = structure  # type: ignore
    config.output.auto_push = auto_push

    config.save(config_path)

    click.echo(f"\nConfiguration saved to {config_path}")

    # Initialize output repository if needed
    repo = config.output.repository
    if not repo.exists() and click.confirm(
        f"\nCreate output repository at {repo}?", default=True
    ):
        repo.mkdir(parents=True, exist_ok=True)
        click.echo(f"Created {repo}")

    # Initialize git if needed
    git_dir = repo / ".git"
    if repo.exists() and not git_dir.exists() and click.confirm(
        "Initialize Git repository?", default=True
    ):
        import subprocess

        subprocess.run(["git", "init"], cwd=repo, check=True)
        click.echo("Initialized Git repository")


@main.command()
@click.option("--dry-run", is_flag=True, help="Show what would be done without making changes")
@click.option("--date", "date_str", help="Sync logs from specific date (YYYY-MM-DD)")
@click.option("--no-commit", is_flag=True, help="Don't commit changes to Git")
@click.option("--no-push", is_flag=True, help="Don't push to remote")
@click.option("--force", "-f", is_flag=True, help="Force full sync, ignore last sync timestamp")
@click.pass_context
def sync(
    ctx: click.Context,
    dry_run: bool,
    date_str: str | None,
    no_commit: bool,
    no_push: bool,
    force: bool,
) -> None:
    """Sync conversation logs to the output repository."""
    from datetime import UTC

    config: Config = ctx.obj["config"]

    # Parse date filter
    date_filter = None
    if date_str:
        try:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            click.echo(f"Invalid date format: {date_str}. Use YYYY-MM-DD.", err=True)
            raise SystemExit(1) from None

    # Get last sync timestamp (unless force or date filter is specified)
    since = None
    if not force and not date_str:
        since = get_last_sync()
        if since:
            click.echo(f"Syncing files modified since {since.isoformat()}")

    if dry_run:
        click.echo("Dry run mode - no changes will be made\n")

    # Run sync
    written_paths = sync_logs(config, date_filter=date_filter, dry_run=dry_run, since=since)

    # Save current timestamp as last sync (unless dry run)
    if not dry_run and written_paths:
        save_last_sync(datetime.now(UTC))

    if not written_paths:
        click.echo("No logs to sync.")
        return

    click.echo(f"{'Would write' if dry_run else 'Wrote'} {len(written_paths)} file(s):")
    for path in written_paths:
        click.echo(f"  - {path}")

    if dry_run:
        return

    # Git operations
    if not no_commit:
        auto_push = config.output.auto_push and not no_push

        # Check repository visibility before pushing
        if auto_push:
            result = check_push_permission(
                config.output.repository,
                allow_public=config.output.allow_public_repository,
                allow_unknown=config.output.allow_unknown_visibility,
            )
            if not result.allowed:
                if result.visibility == RepositoryVisibility.PUBLIC:
                    raise PublicRepositoryError(config.output.repository)
                # UNKNOWN visibility - don't push but continue with commit
                click.echo(f"\nError: {result.warning_message}", err=True)
                auto_push = False
            elif result.warning_message:
                click.echo(f"\nWarning: {result.warning_message}", err=True)

        success = git_commit_and_push(
            config.output.repository,
            config.output.remote,
            config.output.branch,
            auto_push=auto_push,
        )
        if success:
            if auto_push:
                click.echo("\nChanges committed and pushed to remote.")
            else:
                click.echo("\nChanges committed (not pushed).")
        else:
            click.echo("\nWarning: Git operations failed.", err=True)


@main.group()
def config_cmd() -> None:
    """Manage configuration."""
    pass


# Rename to avoid conflict with config module
main.add_command(config_cmd, name="config")


@config_cmd.command(name="show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    """Show current configuration."""
    config: Config = ctx.obj["config"]
    config_path = get_default_config_path()

    click.echo(f"Configuration file: {config_path}")
    click.echo(f"  exists: {config_path.exists()}\n")

    click.echo("[output]")
    click.echo(f"  repository: {config.output.repository}")
    click.echo(f"  structure: {config.output.structure}")
    click.echo(f"  remote: {config.output.remote}")
    click.echo(f"  branch: {config.output.branch}")
    click.echo(f"  auto_push: {config.output.auto_push}")
    click.echo(f"  allow_public_repository: {config.output.allow_public_repository}")
    click.echo(f"  allow_unknown_visibility: {config.output.allow_unknown_visibility}")

    click.echo("\n[sync]")
    click.echo(f"  interval: {config.sync.interval}")
    click.echo(f"  exclude_system: {config.sync.exclude_system}")
    click.echo(f"  exclude_tool_messages: {config.sync.exclude_tool_messages}")

    if config.project_aliases:
        click.echo("\n[projects.aliases]")
        for original, alias in config.project_aliases.items():
            click.echo(f'  "{original}" = "{alias}"')


@config_cmd.command(name="edit")
def config_edit() -> None:
    """Open configuration file in editor."""
    import os
    import subprocess

    config_path = get_default_config_path()

    if not config_path.exists():
        click.echo(f"Configuration file does not exist: {config_path}")
        click.echo("Run 'ccjournal init' to create it.")
        return

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(config_path)])


@main.command(name="list")
@click.option("--limit", "-n", default=10, help="Number of recent logs to show")
@click.pass_context
def list_logs(ctx: click.Context, limit: int) -> None:
    """List recent synced logs."""
    config: Config = ctx.obj["config"]
    repo = config.output.repository

    if not repo.exists():
        click.echo(f"Repository does not exist: {repo}")
        return

    # Find all markdown files
    md_files = sorted(repo.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not md_files:
        click.echo("No logs found.")
        return

    click.echo(f"Recent logs (showing {min(limit, len(md_files))} of {len(md_files)}):\n")

    for md_file in md_files[:limit]:
        rel_path = md_file.relative_to(repo)
        mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
        click.echo(f"  {rel_path}  ({mtime.strftime('%Y-%m-%d %H:%M')})")


@main.group()
@click.pass_context
def daemon(ctx: click.Context) -> None:
    """Manage the sync daemon."""
    pass


@daemon.command(name="start")
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground instead of daemonizing")
@click.pass_context
def daemon_start(ctx: click.Context, foreground: bool) -> None:
    """Start the sync daemon in background."""
    config: Config = ctx.obj["config"]
    status = get_daemon_status()

    if status.running:
        click.echo(f"Daemon is already running (PID: {status.pid})")
        raise SystemExit(1)

    if foreground:
        click.echo("Starting daemon in foreground mode (Ctrl+C to stop)...")
        start_daemon(config, foreground=True)
    else:
        # Print message before daemonizing since parent process exits
        click.echo("Starting daemon in background...")
        start_daemon(config, foreground=False)


@daemon.command(name="stop")
def daemon_stop() -> None:
    """Stop the sync daemon."""
    pid_path = get_pid_file_path()
    status = get_daemon_status(pid_path)

    if not status.running:
        if status.pid is not None:
            click.echo(f"Daemon not running (stale PID file: {status.pid})")
        else:
            click.echo("Daemon not running.")
        raise SystemExit(1)

    click.echo(f"Stopping daemon (PID: {status.pid})...")
    if stop_daemon(pid_path):
        click.echo("Daemon stopped.")
    else:
        click.echo("Failed to stop daemon.", err=True)
        raise SystemExit(1)


@daemon.command(name="status")
def daemon_status_cmd() -> None:
    """Show daemon status."""
    status = get_daemon_status()

    if status.running:
        click.echo(f"Daemon: running (PID: {status.pid})")
    else:
        click.echo("Daemon: not running")

    if status.last_sync:
        click.echo(f"Last sync: {status.last_sync.isoformat()}")
    else:
        click.echo("Last sync: never")

    if status.last_commit:
        click.echo(f"Last commit: {status.last_commit.isoformat()}")
    else:
        click.echo("Last commit: never")


@daemon.command(name="install")
@click.option("--user", is_flag=True, default=True, help="Install for current user only (default)")
@click.pass_context
def daemon_install(ctx: click.Context, user: bool) -> None:
    """Install daemon as system service (launchd/systemd)."""
    import platform
    import shutil

    config: Config = ctx.obj["config"]
    system = platform.system()

    # Find ccjournal executable
    ccjournal_path = shutil.which("ccjournal")
    if not ccjournal_path:
        click.echo("Warning: ccjournal not found in PATH, using default path", err=True)
        ccjournal_path = "/usr/local/bin/ccjournal"

    if system == "Darwin":
        _install_launchd(ccjournal_path, config, user)
    elif system == "Linux":
        _install_systemd(ccjournal_path, config, user)
    else:
        click.echo(f"Automatic setup not supported on {system}.")
        click.echo("Use 'ccjournal daemon start' or schedule with your task scheduler.")


def _install_launchd(ccjournal_path: str, _config: Config, user: bool) -> None:
    """Install launchd service on macOS."""
    plist_path = get_launchd_plist_path(user)
    log_path = get_default_log_path()

    # Ensure directories exist
    log_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    if plist_path.exists() and not click.confirm(
        f"Service file already exists at {plist_path}. Overwrite?"
    ):
        click.echo("Aborted.")
        return

    plist_content = generate_launchd_plist(ccjournal_path, log_path)
    plist_path.write_text(plist_content)

    click.echo(f"Created {plist_path}")
    click.echo("")
    click.echo("To start the service:")
    click.echo(f"  launchctl load {plist_path}")
    click.echo("")
    click.echo("To stop the service:")
    click.echo(f"  launchctl unload {plist_path}")


def _install_systemd(ccjournal_path: str, _config: Config, user: bool) -> None:
    """Install systemd service on Linux."""
    service_path = get_systemd_service_path(user)
    log_path = get_default_log_path()

    # Ensure directories exist
    log_path.parent.mkdir(parents=True, exist_ok=True)
    service_path.parent.mkdir(parents=True, exist_ok=True)

    if service_path.exists() and not click.confirm(
        f"Service file already exists at {service_path}. Overwrite?"
    ):
        click.echo("Aborted.")
        return

    service_content = generate_systemd_service(ccjournal_path, log_path)
    service_path.write_text(service_content)

    click.echo(f"Created {service_path}")
    click.echo("")

    if user:
        click.echo("To enable and start the service:")
        click.echo("  systemctl --user daemon-reload")
        click.echo("  systemctl --user enable ccjournal")
        click.echo("  systemctl --user start ccjournal")
        click.echo("")
        click.echo("To check status:")
        click.echo("  systemctl --user status ccjournal")
    else:
        click.echo("To enable and start the service:")
        click.echo("  sudo systemctl daemon-reload")
        click.echo("  sudo systemctl enable ccjournal")
        click.echo("  sudo systemctl start ccjournal")


if __name__ == "__main__":
    main()
