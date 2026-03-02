import click


@click.group()
def cli():
    """Neural Sieve v3 — Knowledge-to-Skills Pipeline"""
    pass


@cli.command()
def version():
    """Show version."""
    click.echo("neural-sieve-v3 0.1.0")


@cli.command()
@click.option("--port", default=8421)
def serve(port):
    """Start the API server."""
    import uvicorn

    from sieve.config import settings

    uvicorn.run("sieve.api.app:app", host=settings.host, port=port, reload=True)


@cli.command()
@click.option(
    "--by",
    "group_by",
    type=click.Choice(["capsule", "category", "author", "pack"]),
    default="capsule",
    help="Grouping strategy: one skill per capsule, category, author, or pack.",
)
@click.option("--all", "all_capsules", is_flag=True, help="Include all capsules, not just skill-eligible")
@click.option("--output", default=".claude/skills", help="Output directory")
@click.option("--email", default=None, help="User email (falls back to SIEVE_USER_EMAIL env var)")
def compile(group_by, all_capsules, output, email):
    """Compile capsules into Claude Code skill files."""
    import asyncio
    from pathlib import Path

    from sieve.config import settings

    if not settings.openai_api_key:
        raise click.ClickException(
            "SIEVE_OPENAI_API_KEY is not set. Set it in .env or as an environment variable."
        )

    user_email = email or settings.user_email
    if not user_email:
        raise click.ClickException(
            "No user email provided. Use --email or set SIEVE_USER_EMAIL in .env."
        )

    capsules = asyncio.run(_fetch_capsules_from_db(user_email, all_capsules))

    from sieve.compiler.compiler import SkillCompiler

    compiler = SkillCompiler()
    paths = asyncio.run(
        compiler.compile_to_skills(
            output_dir=Path(output),
            by=group_by,
            all_capsules=all_capsules,
            capsules=capsules,
        )
    )
    for p in paths:
        click.echo(f"Generated: {p}")
    click.echo(f"\n{len(paths)} skill(s) compiled.")


async def _fetch_capsules_from_db(email: str, all_capsules: bool = False) -> list[dict]:
    """Fetch capsules from the database for the given user email."""
    from sqlalchemy import select

    from sieve.db.database import async_session
    from sieve.db.models import Capsule, Sieve, User

    async with async_session() as session:
        result = await session.execute(
            select(Sieve.id)
            .join(User, User.id == Sieve.user_id)
            .where(User.email == email)
        )
        sieve_id = result.scalar_one_or_none()
        if not sieve_id:
            raise click.ClickException(f"No sieve found for user {email}")

        stmt = select(Capsule).where(Capsule.sieve_id == sieve_id)
        if not all_capsules:
            stmt = stmt.where(Capsule.skill_eligible == True)  # noqa: E712

        result = await session.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": str(c.id),
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
                "category": c.category or "",
                "domain": c.domain or "",
                "author": c.author or "personal",
                "pack_id": str(c.pack_id) if c.pack_id else None,
                "skill_eligible": c.skill_eligible,
            }
            for c in rows
        ]


@cli.command()
@click.option("--email", default=None, help="User email (auto-detects if only one user)")
def setup(email):
    """Configure Claude Code to use Neural Sieve MCP server."""
    import asyncio

    asyncio.run(_setup_claude_code(email))


async def _setup_claude_code(email: str | None):
    """Write MCP config into ~/.claude/settings.json."""
    import json
    import sys
    from pathlib import Path

    from sqlalchemy import select

    from sieve.config import settings
    from sieve.db.database import async_session
    from sieve.db.models import User

    # Resolve user email
    if not email:
        email = settings.user_email

    if not email:
        async with async_session() as session:
            result = await session.execute(select(User.email))
            emails = [row[0] for row in result.all()]

        if len(emails) == 0:
            click.echo("Error: No users found in the database.", err=True)
            sys.exit(1)
        elif len(emails) == 1:
            email = emails[0]
            click.echo(f"Auto-detected user: {email}")
        else:
            click.echo("Multiple users found. Please choose:")
            for i, e in enumerate(emails, 1):
                click.echo(f"  {i}. {e}")
            choice = click.prompt("Enter number", type=int)
            if 1 <= choice <= len(emails):
                email = emails[choice - 1]
            else:
                click.echo("Invalid choice.", err=True)
                sys.exit(1)

    # Build the MCP config
    db_url = settings.database_url
    mcp_config = {
        "neural-sieve": {
            "command": "uv",
            "args": ["run", "--directory", str(Path.cwd()), "sieve", "mcp"],
            "env": {
                "SIEVE_USER_EMAIL": email,
                "SIEVE_DATABASE_URL": db_url,
            },
        }
    }

    # Read/merge into ~/.claude/settings.json
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        existing = json.loads(settings_path.read_text())
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        existing = {}

    existing.setdefault("mcpServers", {}).update(mcp_config)

    settings_path.write_text(json.dumps(existing, indent=2) + "\n")
    click.echo(f"Wrote MCP config to {settings_path}")
    click.echo("Restart Claude Code for changes to take effect.")


@cli.command()
def mcp():
    """Start MCP server for Claude Code integration."""
    import asyncio

    from sieve.mcp.server import run_server

    asyncio.run(run_server())
