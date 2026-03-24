from pydantic import BaseModel


class CreatorCreate(BaseModel):
    name: str
    slug: str
    description: str
    bio: str = ""
    expertise_domain: str = ""
    avatar_url: str | None = None
    twitter_url: str | None = None
    linkedin_url: str | None = None
    author_url: str | None = None
    topics: list[str] = []
    is_featured: bool = False


class CreatorUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    bio: str | None = None
    expertise_domain: str | None = None
    avatar_url: str | None = None
    twitter_url: str | None = None
    linkedin_url: str | None = None
    author_url: str | None = None
    topics: list[str] | None = None
    is_featured: bool | None = None


class CreatorResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    bio: str
    expertise_domain: str
    avatar_url: str | None
    twitter_url: str | None
    linkedin_url: str | None
    author_url: str | None
    topics: list[str]
    is_featured: bool
    capsule_count: int
    created_at: str


class CreatorListResponse(BaseModel):
    creators: list[CreatorResponse]
    total: int
