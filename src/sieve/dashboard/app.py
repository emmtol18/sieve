"""FastAPI dashboard application."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import Settings
from .routes import create_router

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """Middleware to protect against CSRF attacks.

    Validates that state-changing requests (POST, PUT, DELETE, PATCH) come from
    allowed origins (localhost or browser extensions).
    """

    def __init__(self, app, allowed_origins: set[str | None]):
        super().__init__(app)
        self.allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next):
        # Only check state-changing methods
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")

            # Allow same-origin requests (no Origin header)
            # Allow localhost origins
            # Allow browser extensions (chrome-extension://, moz-extension://)
            is_allowed = (
                origin is None
                or origin in self.allowed_origins
                or origin.startswith("chrome-extension://")
                or origin.startswith("moz-extension://")
            )

            if not is_allowed:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed: invalid origin"},
                )

        return await call_next(request)


def create_app(settings: Settings) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Neural Sieve",
        description="The High-Signal External Memory for AI Influence",
        version="0.1.0",
    )

    # Add CSRF protection middleware with dynamic origins from settings
    app.add_middleware(
        CSRFProtectionMiddleware,
        allowed_origins=settings.get_allowed_origins(),
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
