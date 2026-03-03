from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from sieve.api.auth.deps import get_current_user
from sieve.api.skills.schemas import (
    SkillCompileRequest,
    SkillListResponse,
    SkillResponse,
    SkillUpdate,
)
from sieve.compiler.compiler import SkillCompiler
from sieve.compiler.templates import SKILL_TEMPLATE
from sieve.db.database import get_db
from sieve.db.models import Capsule, Sieve, Skill, SkillCapsule, User

router = APIRouter(prefix="/api/skills", tags=["skills"])


def skill_to_response(s: Skill) -> SkillResponse:
    return SkillResponse(
        id=str(s.id),
        name=s.name,
        title=s.title,
        description=s.description,
        body=s.body,
        status=s.status or "active",
        source_capsule_count=len(s.capsule_links) if s.capsule_links else 0,
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else "",
    )


async def _get_user_sieve(user: User, db: AsyncSession) -> Sieve:
    result = await db.execute(select(Sieve).where(Sieve.user_id == user.id))
    sieve = result.scalar_one_or_none()
    if not sieve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sieve not found")
    return sieve


async def _get_skill_or_404(skill_id: str, sieve: Sieve, db: AsyncSession) -> Skill:
    result = await db.execute(
        select(Skill)
        .where(Skill.id == skill_id, Skill.sieve_id == sieve.id)
        .options(selectinload(Skill.capsule_links))
    )
    skill = result.scalar_one_or_none()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    return skill


@router.post("/compile", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def compile_skill(
    body: SkillCompileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)

    # Load primary capsule
    result = await db.execute(
        select(Capsule).where(
            Capsule.id == body.primary_capsule_id, Capsule.sieve_id == sieve.id
        )
    )
    primary = result.scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Primary capsule not found")

    primary_dict = {
        "title": primary.title,
        "executive_summary": primary.executive_summary,
        "core_insight": primary.core_insight,
        "full_content": primary.full_content,
        "tags": primary.tags or [],
    }

    # Load context capsules
    context_dicts = []
    context_rows = []
    if body.context_capsule_ids:
        result = await db.execute(
            select(Capsule).where(
                Capsule.id.in_([str(cid) for cid in body.context_capsule_ids]),
                Capsule.sieve_id == sieve.id,
            )
        )
        context_rows = list(result.scalars().all())
        context_dicts = [
            {
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
            }
            for c in context_rows
        ]

    compiler = SkillCompiler(api_url="", api_key="")
    skill_data = await compiler.compile_capsules(primary_dict, context_capsules=context_dicts or None)

    skill = Skill(
        sieve_id=sieve.id,
        name=skill_data["name"],
        title=skill_data["title"],
        description=skill_data["description"],
        body=skill_data["body"],
    )
    db.add(skill)
    await db.flush()

    # Create associations
    db.add(SkillCapsule(skill_id=skill.id, capsule_id=primary.id, role="primary"))
    for c in context_rows:
        db.add(SkillCapsule(skill_id=skill.id, capsule_id=c.id, role="context"))

    await db.commit()

    result = await db.execute(
        select(Skill)
        .where(Skill.id == skill.id)
        .options(selectinload(Skill.capsule_links))
    )
    skill = result.scalar_one()

    return skill_to_response(skill)


@router.get("/", response_model=SkillListResponse)
async def list_skills(
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    query = select(Skill).where(Skill.sieve_id == sieve.id, Skill.status == "active")

    if search:
        term = f"%{search}%"
        query = query.where(
            or_(Skill.title.ilike(term), Skill.description.ilike(term), Skill.name.ilike(term))
        )

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Skill.created_at.desc()).offset(offset).limit(limit)
    query = query.options(selectinload(Skill.capsule_links))
    result = await db.execute(query)
    skills = result.scalars().all()

    return SkillListResponse(skills=[skill_to_response(s) for s in skills], total=total)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)
    return skill_to_response(skill)


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    body: SkillUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)

    await db.commit()
    await db.refresh(skill)
    return skill_to_response(skill)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)
    await db.delete(skill)
    await db.commit()


@router.post("/{skill_id}/export")
async def export_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)

    output_dir = Path(".claude/skills")
    output_dir.mkdir(parents=True, exist_ok=True)

    content = SKILL_TEMPLATE.format(name=skill.name, description=skill.description, body=skill.body)
    path = output_dir / f"{skill.name}.md"
    path.write_text(content)

    return {"path": str(path), "message": f"Exported to {path}"}


@router.post("/{skill_id}/recompile", response_model=SkillResponse)
async def recompile_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sieve = await _get_user_sieve(user, db)
    skill = await _get_skill_or_404(skill_id, sieve, db)

    # Load linked capsules
    result = await db.execute(
        select(SkillCapsule).where(SkillCapsule.skill_id == skill.id)
    )
    links = result.scalars().all()

    if not links:
        raise HTTPException(status_code=400, detail="No linked capsules to recompile from")

    primary_link = next((lnk for lnk in links if lnk.role == "primary"), links[0])
    context_links = [lnk for lnk in links if lnk.capsule_id != primary_link.capsule_id]

    # Load capsule data
    result = await db.execute(select(Capsule).where(Capsule.id == primary_link.capsule_id))
    primary = result.scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=400, detail="Primary capsule no longer exists")

    primary_dict = {
        "title": primary.title,
        "executive_summary": primary.executive_summary,
        "core_insight": primary.core_insight,
        "full_content": primary.full_content,
        "tags": primary.tags or [],
    }

    context_dicts = []
    if context_links:
        ctx_ids = [lnk.capsule_id for lnk in context_links]
        result = await db.execute(select(Capsule).where(Capsule.id.in_(ctx_ids)))
        for c in result.scalars().all():
            context_dicts.append({
                "title": c.title,
                "executive_summary": c.executive_summary,
                "core_insight": c.core_insight,
                "full_content": c.full_content,
                "tags": c.tags or [],
            })

    compiler = SkillCompiler(api_url="", api_key="")
    skill_data = await compiler.compile_capsules(primary_dict, context_capsules=context_dicts or None)

    skill.body = skill_data["body"]
    skill.description = skill_data["description"]
    await db.commit()

    result = await db.execute(
        select(Skill)
        .where(Skill.id == skill.id)
        .options(selectinload(Skill.capsule_links))
    )
    skill = result.scalar_one()

    return skill_to_response(skill)
