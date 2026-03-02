import re

from pydantic import BaseModel, field_validator

USERNAME_RE = re.compile(r"^[a-z0-9_]{3,50}$")


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError(
                "Username must be 3-50 characters, lowercase alphanumeric and underscores only"
            )
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    api_key: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    api_key: str
