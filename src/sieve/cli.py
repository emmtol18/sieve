"""Neural Sieve CLI."""

import asyncio
import sys
import time
from pathlib import Path

import click
import httpx

from .config import get_settings
from .logging_config import setup_colored_logging
from .process import ProcessLock, get_service_status


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, verbose):
    """Neural Sieve - The High-Signal External Memory for AI Influence."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    # Note: logging setup is deferred to individual commands
    # MCP command must NOT setup stdout logging (it uses stdio for JSON-RPC)


@cli.command()
@click.option("--force", is_flag=True, help="Overwrite existing files")
def init(force):
    """Initialize a new Neural Sieve vault in the current directory."""
    vault_root = Path.cwd()

    # Create directory structure
    dirs = [
        vault_root / "Inbox",
        vault_root / "Capsules",
        vault_root / "Assets",
        vault_root / "Legacy",
        vault_root / ".sieve",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"  Created: {d.relative_to(vault_root)}/")

    # Create .gitkeep files
    for d in [vault_root / "Inbox", vault_root / "Legacy"]:
        gitkeep = d / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()

    # Create config file
    config_path = vault_root / ".sieve" / "config.yaml"
    if not config_path.exists() or force:
        config_path.write_text(
            """# Neural Sieve Configuration

# Optional: Path to screenshot folder to watch (in addition to Inbox/)
# screenshot_folder: ~/Desktop

# Dashboard port
port: 8420
"""
        )
        click.echo(f"  Created: .sieve/config.yaml")

    # Create .env.example if not exists
    env_example = vault_root / ".env.example"
    if not env_example.exists():
        env_example.write_text(
            """# OpenAI API Key (required)
OPENAI_API_KEY=sk-...

# Optional: Custom screenshot folder
# SIEVE_SCREENSHOT_FOLDER=/Users/yourname/Desktop
"""
        )
        click.echo(f"  Created: .env.example")

    click.echo("")
    click.echo("Vault initialized! Next steps:")
    click.echo("  1. Copy .env.example to .env and add your OpenAI API key")
    click.echo("  2. Run 'sieve start' to launch watcher and dashboard")
    click.echo("  3. Drop files into Inbox/ to process them")


@cli.command()
@click.option("--daemon", is_flag=True, help="Run as background service (for Launch Agent)")
@click.pass_context
def start(ctx, daemon):
    """Start the file watcher and dashboard together.

    This is the recommended way to run Neural Sieve. It launches both
    the file watcher (monitors Inbox/) and the management dashboard
    in a single process with graceful shutdown on Ctrl+C.

    Use --daemon when running via Launch Agent for auto-start on login.
    """
    from .coordinator import ServiceCoordinator

    verbose = ctx.obj.get("verbose", False)

    # Setup logging (to file in daemon mode, to console otherwise)
    if daemon:
        _setup_daemon_logging()
    else:
        setup_colored_logging(verbose)

    try:
        settings = get_settings()
    except Exception as e:
        click.echo(f"Error loading settings: {e}", err=True)
        click.echo("Make sure .env file exists with OPENAI_API_KEY", err=True)
        sys.exit(1)

    coordinator = ServiceCoordinator(settings, verbose=verbose, daemon=daemon)

    try:
        asyncio.run(coordinator.run())
    except KeyboardInterrupt:
        pass  # Handled by signal handler


def _setup_daemon_logging():
    """Setup logging to file for daemon mode."""
    import logging

    settings = get_settings()
    log_file = settings.log_dir / "daemon.log"

    # Configure root logger to file
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
        ],
    )


@cli.command()
@click.pass_context
def watch(ctx):
    """Start the file watcher daemon."""
    from .engine import FileWatcher

    setup_colored_logging(ctx.obj.get("verbose", False))
    click.echo("Starting Neural Sieve watcher...")

    try:
        settings = get_settings()
    except Exception as e:
        click.echo(f"Error loading settings: {e}", err=True)
        click.echo("Make sure .env file exists with OPENAI_API_KEY", err=True)
        sys.exit(1)

    watcher = FileWatcher(settings)

    try:
        asyncio.run(watcher.start())
    except KeyboardInterrupt:
        click.echo("\nStopping watcher...")


@cli.command()
@click.option("--port", "-p", default=None, type=int, help="Port to run on")
@click.pass_context
def manage(ctx, port):
    """Start the management dashboard."""
    from .dashboard import create_app
    import uvicorn

    setup_colored_logging(ctx.obj.get("verbose", False))
    settings = get_settings()
    app = create_app(settings)

    run_port = port or settings.port
    click.echo(f"Starting dashboard at http://{settings.host}:{run_port}")

    uvicorn.run(app, host=settings.host, port=run_port, log_level="info")


@cli.command()
def mcp():
    """Start the MCP server for AI integration.

    This command is typically called by Claude Desktop (via .mcp.json config).
    The MCP server provides tools for searching and accessing your knowledge capsules.
    """
    from .mcp import run_server

    # No stdout output - MCP uses stdio for JSON-RPC
    run_server()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.pass_context
def process(ctx, file_path):
    """Manually process a single file."""
    from .engine import Processor

    setup_colored_logging(ctx.obj.get("verbose", False))
    path = Path(file_path)
    settings = get_settings()
    processor = Processor(settings)

    click.echo(f"Processing: {path.name}")

    async def run():
        result = await processor.process_file(path, capture_method="manual")
        if result:
            click.echo(f"Created: {result}")
        else:
            click.echo("Processing failed. Check .sieve/error.log", err=True)

    asyncio.run(run())


@cli.command()
@click.pass_context
def index(ctx):
    """Regenerate the knowledge index (Capsules/INDEX.md)."""
    from .engine import Indexer

    setup_colored_logging(ctx.obj.get("verbose", False))
    settings = get_settings()
    indexer = Indexer(settings)

    click.echo("Regenerating Capsules/INDEX.md...")

    asyncio.run(indexer.regenerate())
    click.echo("Done!")


@cli.command()
def status():
    """Show status of Neural Sieve services.

    Displays whether the watcher, dashboard, and MCP server are running,
    along with their process IDs and connection URLs.
    """
    try:
        settings = get_settings()
    except Exception:
        click.echo("Error: Could not load settings. Are you in a Neural Sieve vault?", err=True)
        sys.exit(1)

    click.echo("Neural Sieve Status")
    click.echo("=" * 40)

    # Check coordinator process
    services = get_service_status(settings.pid_dir)
    coordinator = services.get("coordinator", {})

    if coordinator.get("running"):
        pid = coordinator.get("pid")
        click.echo(f"  Watcher:   running (PID {pid})")
        click.echo(f"  Dashboard: running (PID {pid})")

        # Test dashboard HTTP connection
        dashboard_url = f"http://{settings.host}:{settings.port}"
        try:
            response = httpx.get(f"{dashboard_url}/", timeout=2.0)
            if response.status_code == 200:
                click.echo(f"             {dashboard_url}")
        except Exception:
            click.echo(f"             {dashboard_url} (not responding)")
    else:
        click.echo("  Watcher:   not running")
        click.echo("  Dashboard: not running")

    # MCP status note
    click.echo("")
    click.echo("  MCP:       managed by Claude Desktop")
    click.echo("             (runs when Claude Desktop connects)")

    # Show vault info
    click.echo("")
    click.echo("Vault Info")
    click.echo("-" * 40)
    click.echo(f"  Location:  {settings.vault_root}")
    click.echo(f"  Inbox:     {settings.inbox_path}")
    click.echo(f"  Capsules:  {settings.capsules_path}")


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Force stop without waiting")
def stop(force):
    """Stop running Neural Sieve services.

    Sends SIGTERM to the running coordinator process for graceful shutdown.
    Use --force to skip waiting for clean shutdown.
    """
    try:
        settings = get_settings()
    except Exception:
        click.echo("Error: Could not load settings. Are you in a Neural Sieve vault?", err=True)
        sys.exit(1)

    lock = ProcessLock("coordinator", settings.pid_dir)

    if not lock.is_locked():
        click.echo("Neural Sieve is not running.")
        return

    pid = lock.get_pid()
    click.echo(f"Stopping Neural Sieve (PID {pid})...")

    if lock.send_shutdown():
        if not force:
            # Wait for process to exit
            for _ in range(10):  # Wait up to 5 seconds
                time.sleep(0.5)
                if not lock.is_locked():
                    break

        if lock.is_locked():
            click.echo("Process still running. Use --force or check logs.", err=True)
            sys.exit(1)
        else:
            click.echo("Stopped.")
    else:
        click.echo("Failed to send stop signal.", err=True)
        sys.exit(1)


@cli.command("install-agent")
def install_agent():
    """Install macOS Launch Agent for auto-start on login.

    Creates a Launch Agent that starts Neural Sieve automatically
    when you log in. The agent runs 'sieve start --daemon'.

    To uninstall, run: sieve uninstall-agent
    """
    import shutil

    try:
        settings = get_settings()
    except Exception:
        click.echo("Error: Could not load settings. Are you in a Neural Sieve vault?", err=True)
        sys.exit(1)

    # Find uv path
    uv_path = shutil.which("uv")
    if not uv_path:
        click.echo("Error: 'uv' not found in PATH. Please install uv first.", err=True)
        sys.exit(1)

    vault_path = str(settings.vault_root.absolute())
    plist_name = "com.neural-sieve.plist"
    plist_dest = Path.home() / "Library" / "LaunchAgents" / plist_name

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.neural-sieve</string>
    <key>ProgramArguments</key>
    <array>
        <string>{uv_path}</string>
        <string>run</string>
        <string>--directory</string>
        <string>{vault_path}</string>
        <string>sieve</string>
        <string>start</string>
        <string>--daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{vault_path}/.sieve/logs/launch-agent.log</string>
    <key>StandardErrorPath</key>
    <string>{vault_path}/.sieve/logs/launch-agent.error.log</string>
    <key>WorkingDirectory</key>
    <string>{vault_path}</string>
</dict>
</plist>
"""

    # Ensure LaunchAgents directory exists
    plist_dest.parent.mkdir(parents=True, exist_ok=True)

    # Ensure log directory exists
    (Path(vault_path) / ".sieve" / "logs").mkdir(parents=True, exist_ok=True)

    # Write plist file
    plist_dest.write_text(plist_content)
    click.echo(f"Created: {plist_dest}")

    # Load the agent
    import subprocess

    result = subprocess.run(
        ["launchctl", "load", str(plist_dest)],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        click.echo("Launch Agent installed and started!")
        click.echo("")
        click.echo("Neural Sieve will now start automatically when you log in.")
        click.echo("Use 'sieve status' to check if it's running.")
    else:
        # Agent might already be loaded
        if "already loaded" in result.stderr.lower() or "already loaded" in result.stdout.lower():
            click.echo("Launch Agent updated. Restart to apply changes.")
        else:
            click.echo(f"Warning: Could not load agent: {result.stderr}", err=True)
            click.echo("You may need to run: launchctl load ~/Library/LaunchAgents/com.neural-sieve.plist")


@cli.command("uninstall-agent")
def uninstall_agent():
    """Uninstall macOS Launch Agent.

    Stops the Launch Agent and removes it from auto-start.
    """
    plist_name = "com.neural-sieve.plist"
    plist_path = Path.home() / "Library" / "LaunchAgents" / plist_name

    if not plist_path.exists():
        click.echo("Launch Agent is not installed.")
        return

    import subprocess

    # Unload the agent
    result = subprocess.run(
        ["launchctl", "unload", str(plist_path)],
        capture_output=True,
        text=True,
    )

    # Remove the plist file
    try:
        plist_path.unlink()
        click.echo(f"Removed: {plist_path}")
        click.echo("Launch Agent uninstalled. Neural Sieve will no longer auto-start.")
    except OSError as e:
        click.echo(f"Error removing {plist_path}: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
