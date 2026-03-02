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
def compile(group_by, all_capsules, output):
    """Compile capsules into Claude Code skill files."""
    import asyncio
    from pathlib import Path

    from sieve.compiler.compiler import SkillCompiler
    from sieve.config import settings

    if not settings.openai_api_key:
        raise click.ClickException(
            "SIEVE_OPENAI_API_KEY is not set. Set it in .env or as an environment variable."
        )
    if not settings.sieve_api_key:
        raise click.ClickException(
            "SIEVE_SIEVE_API_KEY is not set. Set it in .env or as an environment variable."
        )

    compiler = SkillCompiler(api_url=settings.sieve_api_url, api_key=settings.sieve_api_key)
    paths = asyncio.run(
        compiler.compile_to_skills(
            output_dir=Path(output),
            by=group_by,
            all_capsules=all_capsules,
        )
    )
    for p in paths:
        click.echo(f"Generated: {p}")
    click.echo(f"\n{len(paths)} skill(s) compiled.")


@cli.command()
def mcp():
    """Start MCP server for Claude Code integration."""
    import asyncio

    from sieve.mcp.server import run_server

    asyncio.run(run_server())
