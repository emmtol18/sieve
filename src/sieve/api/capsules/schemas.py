from pydantic import BaseModel


class CapsuleCreate(BaseModel):
    title: str
    executive_summary: str = ""
    core_insight: str = ""
    full_content: str = ""
    tags: list[str] = []
    keywords: list[str] = []
    topics: list[str] = []
    category: str = ""
    domain: str = ""
    difficulty: str = "beginner"
    content_type: str = "insight"
    author: str = "personal"
    source_url: str | None = None
    capture_method: str = "manual"
    source_type: str = ""
    pinned: bool = False
    skill_eligible: bool = True


class CapsuleUpdate(BaseModel):
    title: str | None = None
    executive_summary: str | None = None
    core_insight: str | None = None
    full_content: str | None = None
    tags: list[str] | None = None
    keywords: list[str] | None = None
    topics: list[str] | None = None
    category: str | None = None
    domain: str | None = None
    difficulty: str | None = None
    content_type: str | None = None
    pinned: bool | None = None
    skill_eligible: bool | None = None
    status: str | None = None


class CapsuleResponse(BaseModel):
    id: str
    title: str
    executive_summary: str
    core_insight: str
    full_content: str
    tags: list[str]
    keywords: list[str]
    topics: list[str]
    category: str
    domain: str
    difficulty: str
    content_type: str
    author: str
    source_url: str | None
    capture_method: str
    source_type: str
    status: str
    pinned: bool
    skill_eligible: bool
    created_at: str


class CapsuleListResponse(BaseModel):
    capsules: list[CapsuleResponse]
    total: int


class CaptureRequest(BaseModel):
    content: str = ""
    url: str | None = None
    source_url: str | None = None
    images: list[str] = []


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    category: str | None = None
    domain: str | None = None
    difficulty: str | None = None
    author: str | None = None
    pack: str | None = None
