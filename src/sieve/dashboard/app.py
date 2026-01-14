"""FastAPI dashboard application."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Settings
from .routes import create_router

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(settings: Settings) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Neural Sieve",
        description="The High-Signal External Memory for AI Influence",
        version="0.1.0",
    )

    # Ensure directories exist
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    # Mount static files
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Create templates
    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    # Include routes
    router = create_router(settings, templates)
    app.include_router(router)

    return app
