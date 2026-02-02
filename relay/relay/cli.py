"""Relay CLI for key management and server control."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import click

from .config import RelaySettings

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async function synchronously."""
    return asyncio.run(coro)


@click.group()
@click.option(
    "--db",
    "db_path",
    default=None,
    type=click.Path(),
    help="Database path (default: from RELAY_DB_PATH or /opt/sieve-relay/data/relay.db)",
)
@click.pass_context
def cli(ctx, db_path):
    """Sieve Relay - Capture queue management."""
    ctx.ensure_object(dict)
    settings = RelaySettings()
    if db_path:
        settings.db_path = Path(db_path)
    ctx.obj["settings"] = settings


@cli.command("init-db")
@click.pass_context
def init_db_cmd(ctx):
    """Initialize the database tables."""
    from .db import init_db

    settings = ctx.obj["settings"]
    _run_async(init_db(settings.db_path))
    click.echo(f"Database initialized at {settings.db_path}")


@cli.command("generate-key")
@click.option("--name", required=True, help="Name for this key (e.g. 'ios-shortcut')")
@click.option("--admin", is_flag=True, help="Create an admin key (for pull client)")
@click.option("--rate-limit", default=60, help="Requests per hour (default: 60)")
@click.pass_context
def generate_key_cmd(ctx, name, admin, rate_limit):
    """Generate a new API key."""
    from .auth import generate_key
    from .db import get_db

    settings = ctx.obj["settings"]

    async def run():
        db = await get_db(settings.db_path)
        try:
            raw_key = await generate_key(db, name=name, is_admin=admin, rate_limit=rate_limit)
            return raw_key
        finally:
            await db.close()

    raw_key = _run_async(run())

    click.echo("")
    click.echo("API key generated. Save it now — it cannot be retrieved later.")
    click.echo("")
    click.echo(f"  Name:   {name}")
    click.echo(f"  Admin:  {admin}")
    click.echo(f"  Limit:  {rate_limit}/hour")
    click.echo(f"  Key:    {raw_key}")
    click.echo("")


@cli.command("list-keys")
@click.pass_context
def list_keys_cmd(ctx):
    """List all API keys (prefix only, never full key)."""
    from .db import get_db, list_api_keys

    settings = ctx.obj["settings"]

    async def run():
        db = await get_db(settings.db_path)
        try:
            return await list_api_keys(db)
        finally:
            await db.close()

    keys = _run_async(run())

    if not keys:
        click.echo("No API keys found. Use 'relay generate-key' to create one.")
        return

    click.echo(f"{'Name':<20} {'Prefix':<22} {'Admin':<7} {'Active':<8} {'Rate':<8} {'Last Used'}")
    click.echo("-" * 90)

    for key in keys:
        last_used = ""
        if key["last_used_at"]:
            last_used = datetime.fromtimestamp(key["last_used_at"]).strftime("%Y-%m-%d %H:%M")

        click.echo(
            f"{key['name']:<20} "
            f"{key['key_prefix']:<22} "
            f"{'yes' if key['is_admin'] else 'no':<7} "
            f"{'yes' if key['is_active'] else 'REVOKED':<8} "
            f"{key['rate_limit']:<8} "
            f"{last_used}"
        )


@cli.command("revoke-key")
@click.argument("prefix")
@click.pass_context
def revoke_key_cmd(ctx, prefix):
    """Revoke an API key by its prefix."""
    from .db import get_db, revoke_key

    settings = ctx.obj["settings"]

    async def run():
        db = await get_db(settings.db_path)
        try:
            return await revoke_key(db, prefix)
        finally:
            await db.close()

    success = _run_async(run())

    if success:
        click.echo(f"Key with prefix '{prefix}' has been revoked.")
    else:
        click.echo(f"No active key found with prefix '{prefix}'.", err=True)


@cli.command("serve")
@click.pass_context
def serve_cmd(ctx):
    """Start the relay server."""
    import uvicorn

    from .app import create_app

    settings = ctx.obj["settings"]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
