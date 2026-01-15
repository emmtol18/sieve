"""Neural Sieve CLI."""

import asyncio
import sys
from pathlib import Path

import click

from .config import get_settings
from .logging_config import setup_colored_logging


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx, verbose):
    """Neural Sieve - The High-Signal External Memory for AI Influence."""
    setup_colored_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


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
@click.pass_context
def start(ctx):
    """Start the file watcher and dashboard together.

    This is the recommended way to run Neural Sieve. It launches both
    the file watcher (monitors Inbox/) and the management dashboard
    in a single process with graceful shutdown on Ctrl+C.
    """
    from .coordinator import ServiceCoordinator

    verbose = ctx.obj.get("verbose", False)

    try:
        settings = get_settings()
    except Exception as e:
        click.echo(f"Error loading settings: {e}", err=True)
        click.echo("Make sure .env file exists with OPENAI_API_KEY", err=True)
        sys.exit(1)

    coordinator = ServiceCoordinator(settings, verbose=verbose)

    try:
        asyncio.run(coordinator.run())
    except KeyboardInterrupt:
        pass  # Handled by signal handler


@cli.command()
def watch():
    """Start the file watcher daemon."""
    from .engine import FileWatcher

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
def manage(port):
    """Start the management dashboard."""
    from .dashboard import create_app
    import uvicorn

    settings = get_settings()
    app = create_app(settings)

    run_port = port or settings.port
    click.echo(f"Starting dashboard at http://{settings.host}:{run_port}")

    uvicorn.run(app, host=settings.host, port=run_port, log_level="info")


@cli.command()
def mcp():
    """Start the MCP server for AI integration."""
    from .mcp import run_server

    click.echo("Starting MCP server...")
    run_server()


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def process(file_path):
    """Manually process a single file."""
    from .engine import Processor

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
def index():
    """Regenerate the knowledge index (Capsules/INDEX.md)."""
    from .engine import Indexer

    settings = get_settings()
    indexer = Indexer(settings)

    click.echo("Regenerating Capsules/INDEX.md...")

    asyncio.run(indexer.regenerate())
    click.echo("Done!")


if __name__ == "__main__":
    cli()
