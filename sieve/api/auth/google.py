import logging
import re
import secrets

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


def _sanitize_username(raw: str) -> str:
    """Convert a raw string (e.g. email prefix) into a valid username.

    Rules: lowercase, alphanumeric + underscore, 3-50 chars.
    """
    cleaned = re.sub(r"[^a-z0-9_]", "_", raw.lower())
    # Collapse consecutive underscores
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    # Ensure minimum length
    if len(cleaned) < 3:
        cleaned = cleaned + "_user"
    # Truncate to 50 chars
    return cleaned[:50]


async def _generate_unique_username(email: str, db: AsyncSession) -> str:
    """Generate a unique username from an email address.

    Extracts the prefix before @, sanitizes it, and appends a random suffix
    if the base username is already taken.
    """
    prefix = email.split("@")[0]
    base = _sanitize_username(prefix)

    # Try the base username first
    result = await db.execute(select(User).where(User.username == base))
    if not result.scalar_one_or_none():
        return base

    # Append random suffix until unique
    for _ in range(10):
        suffix = secrets.token_hex(2)  # 4-char hex suffix
        candidate = f"{base[:45]}_{suffix}"
        result = await db.execute(select(User).where(User.username == candidate))
        if not result.scalar_one_or_none():
            return candidate

    # Extremely unlikely fallback
    return f"{base[:42]}_{secrets.token_hex(4)}"


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
        username = await _generate_unique_username(email, db)
        user = User(
            email=email,
            password_hash=None,
            display_name=display_name,
            oauth_provider="google",
            username=username,
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
