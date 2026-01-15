"""Shared pytest fixtures for Neural Sieve tests."""

import os
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from sieve.capsule.schema import Capsule, CapsuleMetadata
from sieve.config import Settings


@pytest.fixture
def temp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault directory structure."""
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Inbox").mkdir()
    (vault / "Capsules").mkdir()
    (vault / "Assets").mkdir()
    (vault / "Legacy").mkdir()
    (vault / ".sieve").mkdir()
    return vault


@pytest.fixture
def settings(temp_vault: Path, monkeypatch) -> Settings:
    """Create settings with a temporary vault."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key")
    return Settings(
        vault_root=temp_vault,
        openai_api_key="test-api-key",
    )


@pytest.fixture
def sample_metadata() -> CapsuleMetadata:
    """Create sample capsule metadata."""
    return CapsuleMetadata(
        id="2024-01-15-T100000-123456",
        title="Test Capsule Title",
        source_url="https://example.com/article",
        tags=["testing", "python"],
        category="Technology",
        status="active",
        pinned=False,
        captured_at=date(2024, 1, 15),
        capture_method="manual",
    )


@pytest.fixture
def sample_capsule(sample_metadata: CapsuleMetadata) -> Capsule:
    """Create a complete sample capsule."""
    return Capsule(
        metadata=sample_metadata,
        executive_summary="This is a test capsule for unit testing. It validates the system works.",
        core_insight="Unit tests ensure code quality and prevent regressions.",
        full_content="Full content of the test capsule goes here.\n\nIt can span multiple paragraphs.",
    )


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock()
    return mock


@pytest.fixture
def sample_llm_response() -> dict:
    """Sample LLM response for capsule creation."""
    return {
        "title": "Generated Capsule Title",
        "executive_summary": "AI-generated summary of the content. Key insights extracted.",
        "core_insight": "The main takeaway from this content is significant.",
        "full_content": "The full processed content from the LLM.",
        "tags": ["ai", "knowledge"],
        "category": "Technology",
    }


@pytest.fixture
def sample_html() -> str:
    """Sample HTML content for extraction tests."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Sample Article Title</title>
        <link rel="canonical" href="https://example.com/canonical-url">
    </head>
    <body>
        <nav>Navigation to skip</nav>
        <article>
            <h1>Main Heading</h1>
            <p>This is the main article content.</p>
            <p>It has multiple paragraphs.</p>
        </article>
        <footer>Footer to skip</footer>
    </body>
    </html>
    """


@pytest.fixture
def sample_markdown() -> str:
    """Sample markdown content for extraction tests."""
    return """# Main Title

This is the introduction paragraph.

## Section One

Content of section one.

## Section Two

Content of section two.
"""


@pytest.fixture
def sample_json_capture() -> str:
    """Sample browser extension JSON capture."""
    return """{
    "content": "Captured content from browser",
    "source_url": "https://example.com/page",
    "title": "Browser Captured Title"
}"""
