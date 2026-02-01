"""Entry point for `python -m relay`."""

import logging

import uvicorn

from .app import create_app
from .config import RelaySettings

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    settings = RelaySettings()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")
