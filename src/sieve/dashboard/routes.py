from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sieve.api.auth.deps import verify_token

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")

LOGIN_REDIRECT = RedirectResponse(url="/login", status_code=303)


def _is_authenticated(request: Request) -> bool:
    """Check if the request has a valid sieve_token cookie."""
    token = request.cookies.get("sieve_token")
    if not token:
        return False
    try:
        verify_token(token)
        return True
    except HTTPException:
        return False


def _render(request: Request, template: str, context: dict | None = None) -> HTMLResponse:
    """Render a template after verifying authentication, or redirect to login."""
    ctx = {"request": request, **(context or {})}
    return templates.TemplateResponse(template, ctx)


def _protected(request: Request, template: str, context: dict | None = None) -> HTMLResponse:
    """Render a template if authenticated, otherwise redirect to login."""
    if not _is_authenticated(request):
        return LOGIN_REDIRECT
    return _render(request, template, context)


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return _protected(request, "sieve.html", {"capsules": [], "categories": [], "domains": []})


@router.get("/sieve", response_class=HTMLResponse)
async def sieve_page(request: Request):
    return _protected(request, "sieve.html", {"capsules": [], "categories": [], "domains": []})


@router.get("/capture", response_class=HTMLResponse)
async def capture_page(request: Request):
    return _protected(request, "capture.html")


@router.get("/discover", response_class=HTMLResponse)
async def discover_page(request: Request):
    return _protected(request, "discover.html", {"packs": []})


@router.get("/compile", response_class=HTMLResponse)
async def compile_page(request: Request):
    return _protected(request, "compile.html")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _render(request, "login.html")


@router.get("/capsule/{capsule_id}", response_class=HTMLResponse)
async def capsule_detail(request: Request, capsule_id: str):
    return _protected(
        request, "capsule_detail.html", {"capsule": None, "capsule_id": capsule_id}
    )
