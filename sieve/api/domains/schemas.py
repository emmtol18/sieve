from pydantic import BaseModel


class DomainCreate(BaseModel):
    name: str
    slug: str
    sort_order: int = 0


class DomainResponse(BaseModel):
    id: str
    name: str
    slug: str
    sort_order: int


class DomainListResponse(BaseModel):
    domains: list[DomainResponse]
    total: int
