from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sieve.api.auth.deps import require_admin
from sieve.api.domains.schemas import DomainCreate, DomainListResponse, DomainResponse
from sieve.db.database import get_db
from sieve.db.models import Domain, User

router = APIRouter(prefix="/api/domains", tags=["domains"])


def domain_to_response(domain: Domain) -> DomainResponse:
    return DomainResponse(
        id=str(domain.id),
        name=domain.name,
        slug=domain.slug,
        sort_order=domain.sort_order,
    )


@router.get("/", response_model=DomainListResponse)
async def list_domains(db: AsyncSession = Depends(get_db)) -> DomainListResponse:
    result = await db.execute(select(Domain).order_by(Domain.sort_order))
    domains = result.scalars().all()
    return DomainListResponse(
        domains=[domain_to_response(d) for d in domains],
        total=len(domains),
    )


@router.post("/", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(
    data: DomainCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DomainResponse:
    existing = await db.execute(
        select(Domain).where((Domain.name == data.name) | (Domain.slug == data.slug))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A domain with this name or slug already exists",
        )
    domain = Domain(**data.model_dump())
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return domain_to_response(domain)


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found"
        )
    await db.delete(domain)
    await db.commit()
