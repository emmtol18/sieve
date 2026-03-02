from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sieve.api.auth.google import router as google_auth_router
from sieve.api.auth.routes import router as auth_router
from sieve.api.capsules.routes import router as capsules_router
from sieve.api.capture.routes import router as capture_router
from sieve.api.discover.routes import router as discover_router
from sieve.api.feed.routes import router as feed_router
from sieve.api.sieves.routes import router as sieves_router
from sieve.dashboard.htmx_routes import router as htmx_router
from sieve.dashboard.routes import router as dashboard_router


def create_app() -> FastAPI:
    app = FastAPI(title="Neural Sieve v3", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if request.headers.get("HX-Request"):
            return HTMLResponse(
                content=f'<div class="alert alert-error">{exc.detail}</div>',
                status_code=exc.status_code,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    app.include_router(auth_router)
    app.include_router(google_auth_router)
    app.include_router(capsules_router)
    app.include_router(capture_router)
    app.include_router(sieves_router)
    app.include_router(feed_router)
    app.include_router(discover_router)
    app.include_router(htmx_router)
    app.mount("/static", StaticFiles(directory="src/sieve/dashboard/static"), name="static")
    app.include_router(dashboard_router)
    return app


app = create_app()
