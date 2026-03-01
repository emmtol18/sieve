from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import create_access_token, hash_password, verify_password
from sieve.api.auth.routes import COOKIE_NAME, set_auth_cookie
from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Sieve, User

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="src/sieve/dashboard/templates")


@router.post("/auth/login", response_class=HTMLResponse)
async def htmx_login(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.password_hash):
        html = templates.get_template("partials/auth_message.html").render(
            error="Invalid email or password"
        )
        return HTMLResponse(content=html)

    token = create_access_token(str(user.id))
    html = templates.get_template("partials/auth_message.html").render(
        success="Login successful! Redirecting..."
    )
    response = HTMLResponse(content=html)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    response.headers["HX-Redirect"] = "/sieve"
    return response


@router.post("/auth/signup", response_class=HTMLResponse)
async def htmx_signup(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    email = form.get("email", "")
    password = form.get("password", "")
    display_name = form.get("display_name", "")

    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        html = templates.get_template("partials/auth_message.html").render(
            error="Email already registered"
        )
        return HTMLResponse(content=html)

    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
    )
    db.add(user)
    sieve = Sieve(user_id=user.id, name=f"{display_name}'s Sieve")
    db.add(sieve)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    html = templates.get_template("partials/auth_message.html").render(
        success="Account created! Redirecting..."
    )
    response = HTMLResponse(content=html)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    response.headers["HX-Redirect"] = "/sieve"
    return response


@router.post("/auth/logout", response_class=HTMLResponse)
async def htmx_logout():
    response = HTMLResponse(content="")
    response.delete_cookie(key=COOKIE_NAME, path="/")
    response.headers["HX-Redirect"] = "/login"
    return response
