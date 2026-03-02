import uuid

from sieve.api.skills.schemas import SkillCompileRequest, SkillResponse, SkillUpdate


def test_compile_request_with_context():
    req = SkillCompileRequest(
        primary_capsule_id=uuid.uuid4(),
        context_capsule_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    assert len(req.context_capsule_ids) == 2


def test_compile_request_defaults():
    req = SkillCompileRequest(primary_capsule_id=uuid.uuid4())
    assert req.context_capsule_ids == []


def test_skill_update_partial():
    update = SkillUpdate(title="New Title")
    dumped = update.model_dump(exclude_unset=True)
    assert "title" in dumped
    assert "body" not in dumped


def test_skill_response():
    resp = SkillResponse(
        id=str(uuid.uuid4()),
        name="sieve-test",
        title="Test Skill",
        description="Use when testing",
        body="# Test",
        status="active",
        source_capsule_count=1,
        created_at="2026-03-02T00:00:00",
        updated_at="2026-03-02T00:00:00",
    )
    assert resp.name == "sieve-test"
