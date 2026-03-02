import logging

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Sieve, User

from .deps import create_access_token
from .routes import set_auth_cookie

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/google", tags=["auth-google"])

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def _make_client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )


@router.get("/login")
async def google_login():
    if not _is_configured():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )
    client = _make_client()
    uri, _ = client.create_authorization_url(
        GOOGLE_AUTHORIZE_URL, scope="openid email profile"
    )
    return RedirectResponse(url=uri)


@router.get("/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    if not _is_configured():
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )

    client = _make_client()
    try:
        await client.fetch_token(GOOGLE_TOKEN_URL, code=code)
        resp = await client.get(GOOGLE_USERINFO_URL)
        userinfo = resp.json()
    except Exception:
        logger.exception("Google OAuth callback failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to authenticate with Google",
        )
    finally:
        await client.aclose()

    email = userinfo.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        display_name = userinfo.get("name") or email.split("@")[0]
        user = User(
            email=email,
            password_hash=None,
            display_name=display_name,
            oauth_provider="google",
        )
        db.add(user)
        sieve = Sieve(user_id=user.id, name=f"{display_name}'s Sieve")
        db.add(sieve)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(str(user.id))
    response = RedirectResponse(url="/sieve", status_code=302)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    return response
