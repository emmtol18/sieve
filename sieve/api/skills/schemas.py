from uuid import UUID

from pydantic import BaseModel


class SkillCompileRequest(BaseModel):
    primary_capsule_id: UUID
    context_capsule_ids: list[UUID] = []


class SkillUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    body: str | None = None


class SkillResponse(BaseModel):
    id: str
    name: str
    title: str
    description: str
    body: str
    status: str
    source_capsule_count: int
    created_at: str
    updated_at: str


class SkillListResponse(BaseModel):
    skills: list[SkillResponse]
    total: int
