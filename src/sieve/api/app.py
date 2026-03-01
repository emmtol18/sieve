from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sieve.api.auth.routes import router as auth_router
from sieve.api.capsules.routes import router as capsules_router
from sieve.api.capture.routes import router as capture_router


def create_app() -> FastAPI:
    app = FastAPI(title="Neural Sieve v3", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router)
    app.include_router(capsules_router)
    app.include_router(capture_router)
    return app


app = create_app()
