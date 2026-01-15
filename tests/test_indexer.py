"""Tests for sieve.engine.indexer module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from sieve.engine.indexer import Indexer


class TestIndexer:
    """Tests for Indexer class."""

    @pytest.fixture
    def indexer(self, settings):
        """Create an Indexer instance."""
        return Indexer(settings)

    def _create_capsule(self, settings, category: str, title: str, **metadata):
        """Helper to create a capsule file."""
        category_dir = settings.capsules_path / category
        category_dir.mkdir(parents=True, exist_ok=True)

        meta = {
            "id": title.lower().replace(" ", "-"),
            "title": title,
            "tags": metadata.get("tags", []),
            "category": category,
            "status": metadata.get("status", "active"),
            "pinned": metadata.get("pinned", False),
            "captured_at": metadata.get("captured_at", "2024-01-15"),
        }

        content = f"""---
{yaml.dump(meta)}---

# Content

Test content for {title}
"""
        slug = title.lower().replace(" ", "_")[:20]
        path = category_dir / f"{slug}.md"
        path.write_text(content, encoding="utf-8")
        return path

    async def test_regenerate_creates_readme(self, indexer, settings):
        """Test that regenerate creates README.md."""
        self._create_capsule(settings, "Tech", "Test Capsule")

        await indexer.regenerate()

        assert settings.readme_path.exists()

    async def test_regenerate_includes_title(self, indexer, settings):
        """Test that README includes Neural Sieve title."""
        self._create_capsule(settings, "Tech", "Test")

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "# Neural Sieve" in content
        assert "High-Signal External Memory" in content

    async def test_regenerate_includes_timestamp(self, indexer, settings):
        """Test that README includes last updated timestamp."""
        self._create_capsule(settings, "Tech", "Test")

        with patch("sieve.engine.indexer.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 6, 15, 14, 30)
            await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "2024-06-15 14:30" in content

    async def test_regenerate_groups_by_category(self, indexer, settings):
        """Test that capsules are grouped by category."""
        self._create_capsule(settings, "Technology", "Tech Article")
        self._create_capsule(settings, "Science", "Science Article")
        self._create_capsule(settings, "Technology", "Another Tech")

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "### Technology" in content
        assert "### Science" in content

    async def test_regenerate_sorts_categories_alphabetically(self, indexer, settings):
        """Test that categories are sorted alphabetically."""
        self._create_capsule(settings, "Zebra", "Z Article")
        self._create_capsule(settings, "Apple", "A Article")
        self._create_capsule(settings, "Mango", "M Article")

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        apple_pos = content.find("### Apple")
        mango_pos = content.find("### Mango")
        zebra_pos = content.find("### Zebra")

        assert apple_pos < mango_pos < zebra_pos

    async def test_regenerate_pinned_section(self, indexer, settings):
        """Test that pinned capsules appear in Eternal Truths section."""
        self._create_capsule(settings, "Tech", "Regular", pinned=False)
        self._create_capsule(settings, "Wisdom", "Pinned Wisdom", pinned=True)

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "## Eternal Truths" in content
        assert "[pinned]" in content
        assert "Pinned Wisdom" in content

    async def test_regenerate_no_pinned_section_if_none(self, indexer, settings):
        """Test that Eternal Truths section is omitted if no pinned capsules."""
        self._create_capsule(settings, "Tech", "Regular", pinned=False)

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "## Eternal Truths" not in content

    async def test_regenerate_includes_tags(self, indexer, settings):
        """Test that tags are included in the index."""
        self._create_capsule(settings, "Tech", "Tagged Article", tags=["python", "testing"])

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "`python`" in content
        assert "`testing`" in content

    async def test_regenerate_includes_stats(self, indexer, settings):
        """Test that statistics are included."""
        self._create_capsule(settings, "Tech", "Article 1")
        self._create_capsule(settings, "Tech", "Article 2")
        self._create_capsule(settings, "Science", "Article 3")
        self._create_capsule(settings, "Wisdom", "Pinned", pinned=True)

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "**Total capsules:** 4" in content
        assert "**Categories:** 3" in content
        assert "**Pinned:** 1" in content

    async def test_regenerate_limits_per_category(self, indexer, settings):
        """Test that only 20 capsules per category are shown."""
        for i in range(25):
            self._create_capsule(
                settings,
                "Tech",
                f"Article {i:02d}",
                captured_at=f"2024-01-{i+1:02d}",
            )

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "...and 5 more" in content

    async def test_regenerate_excludes_legacy(self, indexer, settings):
        """Test that legacy capsules are excluded."""
        self._create_capsule(settings, "Tech", "Active Article", status="active")
        self._create_capsule(settings, "Tech", "Legacy Article", status="legacy")

        await indexer.regenerate()

        content = settings.readme_path.read_text()
        assert "Active Article" in content
        assert "Legacy Article" not in content

    async def test_format_capsule_line(self, indexer, settings):
        """Test the capsule line formatting."""
        capsule = {
            "title": "Test Title",
            "_path": "Capsules/Tech/test.md",
            "tags": ["tag1", "tag2"],
            "pinned": False,
        }

        line = indexer._format_capsule_line(capsule)

        assert line == "- [Test Title](Capsules/Tech/test.md) `tag1` `tag2`"

    async def test_format_capsule_line_pinned(self, indexer, settings):
        """Test formatting of pinned capsule."""
        capsule = {
            "title": "Pinned Title",
            "_path": "Capsules/Wisdom/pinned.md",
            "tags": [],
            "pinned": True,
        }

        line = indexer._format_capsule_line(capsule)

        assert "[pinned]" in line
        assert "[Pinned Title]" in line

    async def test_format_capsule_line_no_tags(self, indexer, settings):
        """Test formatting without tags."""
        capsule = {
            "title": "No Tags",
            "_path": "path.md",
            "tags": [],
            "pinned": False,
        }

        line = indexer._format_capsule_line(capsule)

        assert line == "- [No Tags](path.md)"
        assert "`" not in line
