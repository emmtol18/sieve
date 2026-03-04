import uuid

from sieve.db.models import Skill, SkillCapsule


def test_skill_model_has_required_columns():
    skill = Skill(
        sieve_id=uuid.uuid4(),
        name="sieve-deep-work",
        title="Deep Work",
        description="Use when working on focus techniques",
        body="## Overview\nDeep work is...",
    )
    assert skill.name == "sieve-deep-work"
    assert skill.title == "Deep Work"
    assert skill.status == "active"
    assert skill.id is not None


def test_skill_capsule_association():
    assoc = SkillCapsule(
        skill_id=uuid.uuid4(),
        capsule_id=uuid.uuid4(),
        role="primary",
    )
    assert assoc.role == "primary"


def test_skill_default_values():
    skill = Skill(
        sieve_id=uuid.uuid4(),
        name="test",
        title="Test",
        description="desc",
        body="body",
    )
    assert skill.status == "active"
    assert skill.created_at is not None
