from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.config import settings
from sieve.db.database import get_db
from sieve.db.models import Sieve, User

from .deps import create_access_token, get_current_user, hash_password, verify_password
from .schemas import LoginRequest, SignupRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "sieve_token"


def set_auth_cookie(response: Response, token: str, max_age_days: int = 7, secure: bool = False) -> None:
    """Set the sieve_token HTTP-only cookie on a response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=max_age_days * 86400,
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        username=body.username,
    )
    db.add(user)

    sieve = Sieve(
        user_id=user.id,
        name=f"{body.display_name}'s Sieve",
    )
    db.add(sieve)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    data = TokenResponse(access_token=token, api_key=str(user.api_key))
    response = JSONResponse(content=data.model_dump(), status_code=201)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    return response


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(str(user.id))
    data = TokenResponse(access_token=token, api_key=str(user.api_key))
    response = JSONResponse(content=data.model_dump(), status_code=200)
    set_auth_cookie(response, token, max_age_days=settings.jwt_expiry_days)
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        api_key=str(user.api_key),
    )
