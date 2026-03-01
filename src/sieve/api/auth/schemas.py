from pydantic import BaseModel


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str


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
