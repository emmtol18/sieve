from click.testing import CliRunner

from sieve.compiler.compiler import SkillCompiler, _slugify
from sieve.compiler.templates import (
    COMPILE_GROUP_PROMPT,
    COMPILE_SINGLE_PROMPT,
    DESCRIPTION_PROMPT,
    SKILL_TEMPLATE,
)


def test_skill_template_renders():
    rendered = SKILL_TEMPLATE.format(
        name="test-skill",
        description="Use when testing skill compilation",
        body="## Overview\nA test skill.\n\n## When to Use\n- Testing",
    )
    assert "name: test-skill" in rendered
    assert "Use when" in rendered
    assert "## Overview" in rendered


def test_single_prompt_renders():
    rendered = COMPILE_SINGLE_PROMPT.format(
        title="Effective Prompting",
        tags="ai, prompts",
        core_insight="Be specific",
        executive_summary="How to write better prompts",
        full_content="Full content here...",
    )
    assert "Effective Prompting" in rendered
    assert "Be specific" in rendered
    assert "Overview" in rendered
    assert "Quick Reference" in rendered


def test_group_prompt_renders():
    rendered = COMPILE_GROUP_PROMPT.format(
        author="karpathy",
        capsules_text="### Test\nTags: ai\nInsight: test\n",
    )
    assert "karpathy" in rendered
    assert "### Test" in rendered
    assert "Core Principles" in rendered


def test_description_prompt_renders():
    rendered = DESCRIPTION_PROMPT.format(
        title="Cloud Deployment",
        summary="How to deploy apps to the cloud",
    )
    assert "Cloud Deployment" in rendered
    assert "Use when" in rendered


def test_slugify():
    assert _slugify("Hello World") == "hello-world"
    assert _slugify("Effective LLM Prompting!") == "effective-llm-prompting"
    assert _slugify("  spaces  and--dashes  ") == "spaces-and-dashes"
    assert _slugify("UPPER CASE") == "upper-case"
    assert _slugify("special@chars#here") == "specialcharshere"


def test_compiler_group_by_author():
    capsules = [
        {"author": "karpathy", "title": "A", "tags": ["ai"]},
        {"author": "karpathy", "title": "B", "tags": ["ml"]},
        {"author": "personal", "title": "C", "tags": ["dev"]},
    ]
    compiler = SkillCompiler(api_url="http://localhost:8421", api_key="test")
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
    compiler = SkillCompiler(api_url="http://localhost:8421", api_key="test")
    groups = compiler.group_capsules(capsules, by="category")
    assert len(groups["AI"]) == 2
    assert len(groups["Business"]) == 1


def test_compiler_group_unknown_key():
    capsules = [{"title": "A"}, {"title": "B"}]
    compiler = SkillCompiler(api_url="http://localhost:8421", api_key="test")
    groups = compiler.group_capsules(capsules, by="author")
    assert "unknown" in groups
    assert len(groups["unknown"]) == 2


def test_cli_compile_missing_openai_key(monkeypatch):
    """Compile should fail with clear error when SIEVE_OPENAI_API_KEY is not set."""
    from sieve.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "sieve_api_key", "some-key")

    from sieve.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["compile"])
    assert result.exit_code != 0
    assert "SIEVE_OPENAI_API_KEY" in result.output


def test_cli_compile_missing_sieve_key(monkeypatch):
    """Compile should fail with clear error when SIEVE_SIEVE_API_KEY is not set."""
    from sieve.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "some-key")
    monkeypatch.setattr(settings, "sieve_api_key", "")

    from sieve.cli import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["compile"])
    assert result.exit_code != 0
    assert "SIEVE_SIEVE_API_KEY" in result.output
