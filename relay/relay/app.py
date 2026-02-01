"""FastAPI application for the relay server."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import RelaySettings
from .db import get_db, init_db
from .routes import create_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage DB connection lifecycle."""
    settings: RelaySettings = app.state.settings
    await init_db(settings.db_path)
    app.state.db = await get_db(settings.db_path)
    logger.info(f"[RELAY] Server ready on {settings.host}:{settings.port}")
    yield
    await app.state.db.close()
    logger.info("[RELAY] Database connection closed")


def create_app(settings: RelaySettings | None = None) -> FastAPI:
    """Create the FastAPI relay application."""
    if settings is None:
        settings = RelaySettings()

    app = FastAPI(
        title="Sieve Relay",
        description="Minimal capture relay for Neural Sieve",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.settings = settings

    # CORS: allow browser extensions and any tunnel origin
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    router = create_router()
    app.include_router(router)

    return app
