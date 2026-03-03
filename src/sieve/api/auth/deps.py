from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt_mod
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import User

# ---------------------------------------------------------------------------
# Monkey-patch passlib/bcrypt compatibility (passlib is unmaintained and
# incompatible with bcrypt>=4).  We must patch *before* importing
# passlib.context so the backend detection succeeds.
# ---------------------------------------------------------------------------
if not hasattr(_bcrypt_mod, "__about__"):

    class _About:
        __version__ = _bcrypt_mod.__version__ if hasattr(_bcrypt_mod, "__version__") else "4.0.0"

    _bcrypt_mod.__about__ = _About  # type: ignore[attr-defined]

# Wrap hashpw/checkpw to silently truncate passwords > 72 bytes (passlib's
# internal wrap-bug detection test sends a 234-byte password).
_orig_hashpw = _bcrypt_mod.hashpw
_orig_checkpw = _bcrypt_mod.checkpw


def _patched_hashpw(password: bytes, salt: bytes) -> bytes:
    return _orig_hashpw(password[:72], salt)


def _patched_checkpw(password: bytes, hashed_password: bytes) -> bool:
    return _orig_checkpw(password[:72], hashed_password)


_bcrypt_mod.hashpw = _patched_hashpw  # type: ignore[assignment]
_bcrypt_mod.checkpw = _patched_checkpw  # type: ignore[assignment]
# ---------------------------------------------------------------------------

from passlib.context import CryptContext  # noqa: E402

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expiry_days)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> str:
    """Decode a JWT and return the user_id (``sub`` claim).

    Raises ``HTTPException(401)`` on any decoding failure or missing subject.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_id


def get_token_from_request(request: Request) -> str | None:
    """Extract JWT token from cookie first, then Authorization header."""
    token = request.cookies.get("sieve_token")
    if token:
        return token
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    token = get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user_id = verify_token(token)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def get_current_user_by_api_key(
    api_key: str,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(select(User).where(User.api_key == api_key))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user
