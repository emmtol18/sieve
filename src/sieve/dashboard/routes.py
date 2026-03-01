from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt

from sieve.config import settings

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")


def _is_authenticated(request: Request) -> bool:
    """Check if the request has a valid sieve_token cookie."""
    token = request.cookies.get("sieve_token")
    if not token:
        return False
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub") is not None
    except JWTError:
        return False


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "sieve.html", {"request": request, "capsules": [], "categories": [], "domains": []}
    )


@router.get("/sieve", response_class=HTMLResponse)
async def sieve_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "sieve.html", {"request": request, "capsules": [], "categories": [], "domains": []}
    )


@router.get("/capture", response_class=HTMLResponse)
async def capture_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("capture.html", {"request": request})


@router.get("/discover", response_class=HTMLResponse)
async def discover_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("discover.html", {"request": request, "packs": []})


@router.get("/compile", response_class=HTMLResponse)
async def compile_page(request: Request):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("compile.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/capsule/{capsule_id}", response_class=HTMLResponse)
async def capsule_detail(request: Request, capsule_id: str):
    if not _is_authenticated(request):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "capsule_detail.html", {"request": request, "capsule": None, "capsule_id": capsule_id}
    )
