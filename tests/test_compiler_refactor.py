import pytest

from sieve.compiler.compiler import SkillCompiler, _slugify


def test_slugify():
    assert _slugify("Deep Work Techniques") == "deep-work-techniques"
    assert _slugify("Hello! World?") == "hello-world"


@pytest.mark.asyncio
async def test_compile_capsule_returns_dict():
    """compile_capsule should return a dict with name, title, description, body."""
    compiler = SkillCompiler.__new__(SkillCompiler)

    async def fake_compile_single(capsule):
        return "## Overview\nFake skill body"

    async def fake_generate_description(title, summary):
        return "Use when testing skill compilation"

    compiler.compile_single = fake_compile_single
    compiler._generate_description = fake_generate_description

    capsule = {
        "title": "Deep Work",
        "executive_summary": "Focus techniques for productivity",
        "core_insight": "Deep work is valuable",
        "full_content": "Full content here",
        "tags": ["productivity", "focus"],
    }

    result = await compiler.compile_capsule(capsule)

    assert result["name"] == "sieve-deep-work"
    assert result["title"] == "Deep Work"
    assert result["description"] == "Use when testing skill compilation"
    assert "Fake skill body" in result["body"]


@pytest.mark.asyncio
async def test_compile_capsules_with_context():
    """compile_capsules should handle primary + context capsules."""
    compiler = SkillCompiler.__new__(SkillCompiler)

    async def fake_compile_single(capsule):
        return "## Overview\nSingle capsule skill"

    async def fake_compile_group(label, capsules):
        return f"## Overview\nGroup skill from {len(capsules)} capsules"

    async def fake_generate_description(title, summary):
        return "Use when testing"

    compiler.compile_single = fake_compile_single
    compiler.compile_group = fake_compile_group
    compiler._generate_description = fake_generate_description

    primary = {
        "title": "Primary Capsule",
        "executive_summary": "Primary summary",
        "core_insight": "Primary insight",
        "full_content": "Primary content",
        "tags": ["test"],
    }
    context = [
        {
            "title": "Context 1",
            "executive_summary": "Context summary",
            "core_insight": "Context insight",
            "full_content": "Context content",
            "tags": [],
        }
    ]

    result = await compiler.compile_capsules(primary, context_capsules=context)
    assert result["name"] == "sieve-primary-capsule"
    assert "2 capsules" in result["body"]
