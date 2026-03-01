from sieve.compiler.compiler import SkillCompiler
from sieve.compiler.templates import SKILL_TEMPLATE, COMPILE_PROMPT


def test_skill_template_renders():
    rendered = SKILL_TEMPLATE.format(
        name="test-skill",
        description="A test skill",
        body="## Principles\n1. Be simple\n2. Ship fast",
    )
    assert "name: test-skill" in rendered
    assert "## Principles" in rendered
    assert "Be simple" in rendered


def test_compile_prompt_renders():
    rendered = COMPILE_PROMPT.format(
        author="karpathy",
        capsules_text="### Test\nTags: ai\nInsight: test\n",
    )
    assert "karpathy" in rendered
    assert "### Test" in rendered


def test_compiler_group_by_author():
    capsules = [
        {"author": "karpathy", "title": "A", "tags": ["ai"]},
        {"author": "karpathy", "title": "B", "tags": ["ml"]},
        {"author": "personal", "title": "C", "tags": ["dev"]},
    ]
    compiler = SkillCompiler(api_url="http://localhost:8420", api_key="test")
    groups = compiler.group_capsules(capsules, by="author")
    assert "karpathy" in groups
    assert len(groups["karpathy"]) == 2
    assert "personal" in groups
    assert len(groups["personal"]) == 1


def test_compiler_group_by_category():
    capsules = [
        {"category": "AI", "title": "A"},
        {"category": "AI", "title": "B"},
        {"category": "Business", "title": "C"},
    ]
    compiler = SkillCompiler(api_url="http://localhost:8420", api_key="test")
    groups = compiler.group_capsules(capsules, by="category")
    assert len(groups["AI"]) == 2
    assert len(groups["Business"]) == 1


def test_compiler_group_unknown_key():
    capsules = [{"title": "A"}, {"title": "B"}]
    compiler = SkillCompiler(api_url="http://localhost:8420", api_key="test")
    groups = compiler.group_capsules(capsules, by="author")
    assert "unknown" in groups
    assert len(groups["unknown"]) == 2
