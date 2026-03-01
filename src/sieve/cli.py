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
@click.option("--port", default=8420)
def serve(port):
    """Start the API server."""
    import uvicorn

    from sieve.config import settings

    uvicorn.run("sieve.api.app:app", host=settings.host, port=port, reload=True)


@cli.command()
@click.option("--pack", help="Compile a specific leader pack")
@click.option("--personal", is_flag=True, help="Compile personal capsules only")
@click.option("--all", "all_capsules", is_flag=True, help="Compile everything")
@click.option("--output", default=".claude/skills", help="Output directory")
def compile(pack, personal, all_capsules, output):
    """Compile capsules into Claude Code skill files."""
    import asyncio
    from pathlib import Path

    from sieve.compiler.compiler import SkillCompiler
    from sieve.config import settings

    compiler = SkillCompiler(api_url=settings.sieve_api_url, api_key=settings.sieve_api_key)
    paths = asyncio.run(
        compiler.compile_to_skills(
            output_dir=Path(output),
            pack=pack,
            personal=personal,
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
