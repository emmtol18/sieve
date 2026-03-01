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
