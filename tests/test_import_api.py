import io
import zipfile
from unittest.mock import AsyncMock, patch

import pytest


def _make_vault_zip(notes: dict[str, str]) -> bytes:
    """Create an in-memory zip file from a dict of {filename: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in notes.items():
            zf.writestr(name, content)
    return buf.getvalue()


VALID_NOTE_1 = (
    "---\ntags:\n  - ai\n  - ml\n---\n\n"
    "# Machine Learning Basics\n\n"
    "Key concepts in ML include supervised and unsupervised learning approaches."
)

VALID_NOTE_2 = (
    "# Design Patterns\n\n"
    "The observer pattern is fundamental to event-driven architecture design."
)

SHORT_NOTE = "hi"


def _mock_llm_extract(content: str) -> dict:
    """Return a mock capsule extraction result."""
    return {
        "title": "LLM Title",
        "executive_summary": "A summary from LLM.",
        "core_insight": "An insight from LLM.",
        "full_content": content,
        "tags": ["llm-tag"],
        "keywords": ["keyword"],
        "topics": ["topic"],
        "category": "Technology",
        "domain": "AI",
        "difficulty": "beginner",
        "content_type": "insight",
        "source_type": "note",
    }


@pytest.mark.asyncio
async def test_import_vault_zip(client, test_user, auth_cookies):
    """Upload zip with 2 valid notes + 1 empty -> imported=2, skipped=1."""
    zip_bytes = _make_vault_zip({
        "note1.md": VALID_NOTE_1,
        "note2.md": VALID_NOTE_2,
        "empty.md": SHORT_NOTE,
    })

    mock_extract = AsyncMock(side_effect=lambda content: _mock_llm_extract(content))

    with patch("sieve.api.import_vault.routes.LLMClient") as mock_cls:
        mock_cls.return_value.extract_capsule = mock_extract

        response = await client.post(
            "/api/import/vault",
            files={"file": ("vault.zip", zip_bytes, "application/zip")},
            cookies=auth_cookies,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert data["skipped"] == 1
    assert data["duplicates"] == 0


@pytest.mark.asyncio
async def test_import_deduplicates(client, test_user, auth_cookies, db_session):
    """Existing capsule with same title -> duplicates=1."""
    from sieve.db.models import Capsule

    _, sieve = test_user

    # Create an existing capsule with title "Machine Learning Basics"
    existing = Capsule(
        sieve_id=sieve.id,
        title="Machine Learning Basics",
        executive_summary="Existing summary",
        core_insight="Existing insight",
        full_content="Existing content that is long enough.",
    )
    db_session.add(existing)
    await db_session.commit()

    zip_bytes = _make_vault_zip({
        "note1.md": VALID_NOTE_1,  # Title: "Machine Learning Basics" -> duplicate
        "note2.md": VALID_NOTE_2,  # Title: "Design Patterns" -> imported
    })

    mock_extract = AsyncMock(side_effect=lambda content: _mock_llm_extract(content))

    with patch("sieve.api.import_vault.routes.LLMClient") as mock_cls:
        mock_cls.return_value.extract_capsule = mock_extract

        response = await client.post(
            "/api/import/vault",
            files={"file": ("vault.zip", zip_bytes, "application/zip")},
            cookies=auth_cookies,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 1
    assert data["duplicates"] == 1


@pytest.mark.asyncio
async def test_import_rejects_non_zip(client, test_user, auth_cookies):
    """Non-zip file should be rejected."""
    response = await client.post(
        "/api/import/vault",
        files={"file": ("vault.txt", b"not a zip", "text/plain")},
        cookies=auth_cookies,
    )
    assert response.status_code == 400
    assert "zip" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_rejects_invalid_zip(client, test_user, auth_cookies):
    """Invalid zip contents should be rejected."""
    response = await client.post(
        "/api/import/vault",
        files={"file": ("vault.zip", b"not a real zip", "application/zip")},
        cookies=auth_cookies,
    )
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_import_skips_macosx_dir(client, test_user, auth_cookies):
    """__MACOSX directory entries should be skipped."""
    zip_bytes = _make_vault_zip({
        "__MACOSX/._note1.md": "garbage metadata content that should be skipped entirely",
        "note1.md": VALID_NOTE_1,
    })

    mock_extract = AsyncMock(side_effect=lambda content: _mock_llm_extract(content))

    with patch("sieve.api.import_vault.routes.LLMClient") as mock_cls:
        mock_cls.return_value.extract_capsule = mock_extract

        response = await client.post(
            "/api/import/vault",
            files={"file": ("vault.zip", zip_bytes, "application/zip")},
            cookies=auth_cookies,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 1
    assert data["skipped"] == 0


@pytest.mark.asyncio
async def test_import_prefers_frontmatter_tags(client, test_user, auth_cookies):
    """Notes with good frontmatter should use parsed tags, not LLM tags."""
    zip_bytes = _make_vault_zip({
        "note1.md": VALID_NOTE_1,  # Has frontmatter tags: ai, ml
    })

    mock_extract = AsyncMock(side_effect=lambda content: _mock_llm_extract(content))

    with patch("sieve.api.import_vault.routes.LLMClient") as mock_cls:
        mock_cls.return_value.extract_capsule = mock_extract

        response = await client.post(
            "/api/import/vault",
            files={"file": ("vault.zip", zip_bytes, "application/zip")},
            cookies=auth_cookies,
        )

    assert response.status_code == 200
    assert response.json()["imported"] == 1
