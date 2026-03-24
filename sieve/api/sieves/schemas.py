from pydantic import BaseModel


class SieveProfileResponse(BaseModel):
    id: str
    name: str
    username: str
    display_name: str
    bio: str
    avatar_url: str | None
    is_public: bool
    capsule_count: int
    follower_count: int
    following_count: int
    created_at: str


class SieveUpdateRequest(BaseModel):
    name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    is_public: bool | None = None
