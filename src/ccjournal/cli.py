"""CLI interface for ccjournal."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import click

from . import __version__
from .config import Config, get_default_config_path
from .sync import git_commit_and_push, sync_logs


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
@click.pass_context
def sync(
    ctx: click.Context,
    dry_run: bool,
    date_str: str | None,
    no_commit: bool,
    no_push: bool,
) -> None:
    """Sync conversation logs to the output repository."""
    config: Config = ctx.obj["config"]

    # Parse date filter
    date_filter = None
    if date_str:
        try:
            date_filter = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            click.echo(f"Invalid date format: {date_str}. Use YYYY-MM-DD.", err=True)
            raise SystemExit(1) from None

    if dry_run:
        click.echo("Dry run mode - no changes will be made\n")

    # Run sync
    written_paths = sync_logs(config, date_filter=date_filter, dry_run=dry_run)

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

    click.echo("\n[sync]")
    click.echo(f"  interval: {config.sync.interval}")
    click.echo(f"  exclude_system: {config.sync.exclude_system}")

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
def daemon() -> None:
    """Manage the sync daemon."""
    pass


@daemon.command(name="start")
def daemon_start() -> None:
    """Start the sync daemon in background."""
    # TODO: Implement daemon functionality
    click.echo("Daemon functionality not yet implemented.")
    click.echo("For now, use 'ccjournal sync' with cron or launchd.")


@daemon.command(name="stop")
def daemon_stop() -> None:
    """Stop the sync daemon."""
    click.echo("Daemon functionality not yet implemented.")


@daemon.command(name="status")
def daemon_status() -> None:
    """Show daemon status."""
    click.echo("Daemon functionality not yet implemented.")


@daemon.command(name="install")
@click.option("--user", is_flag=True, default=True, help="Install for current user only (default)")
def daemon_install(user: bool) -> None:
    """Install daemon as system service (launchd/systemd)."""
    import platform

    system = platform.system()
    install_type = "user" if user else "system"

    if system == "Darwin":
        click.echo(f"To set up automatic sync on macOS ({install_type} installation):")
        click.echo("")
        click.echo("1. Create ~/Library/LaunchAgents/com.ccjournal.sync.plist")
        click.echo("2. Add the following content:")
        click.echo("")
        plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ccjournal.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ccjournal</string>
        <string>sync</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>"""
        click.echo(plist_content)
        click.echo("")
        click.echo("3. Load with: launchctl load ~/Library/LaunchAgents/com.ccjournal.sync.plist")

    elif system == "Linux":
        click.echo("To set up automatic sync on Linux, add to systemd:")
        click.echo("")
        click.echo("1. Create ~/.config/systemd/user/ccjournal.service")
        click.echo("2. Create ~/.config/systemd/user/ccjournal.timer")
        click.echo("")
        click.echo("See documentation for details.")

    else:
        click.echo(f"Automatic setup not supported on {system}.")
        click.echo("Use cron or task scheduler to run 'ccjournal sync' periodically.")


if __name__ == "__main__":
    main()
