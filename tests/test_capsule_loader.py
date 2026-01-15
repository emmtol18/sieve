"""Tests for sieve.capsule.loader module."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from sieve.capsule.loader import find_capsule_file, load_capsules


class TestLoadCapsules:
    """Tests for load_capsules function."""

    def _create_capsule_file(self, settings, category: str, name: str, **metadata):
        """Helper to create a capsule file."""
        category_dir = settings.capsules_path / category
        category_dir.mkdir(parents=True, exist_ok=True)

        default_meta = {
            "id": name,
            "title": f"Title for {name}",
            "tags": [],
            "category": category,
            "status": "active",
            "pinned": False,
            "captured_at": "2024-01-15",
        }
        default_meta.update(metadata)

        content = f"""---
{yaml.dump(default_meta)}---

# Executive Summary

Test summary for {name}

# Core Insight

Test insight

# Full Content

Test content
"""
        path = category_dir / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def test_returns_empty_list_if_no_capsules_dir(self, settings):
        """Test that empty list is returned if Capsules directory doesn't exist."""
        import shutil
        shutil.rmtree(settings.capsules_path)

        result = load_capsules(settings)

        assert result == []

    def test_loads_single_capsule(self, settings):
        """Test loading a single capsule."""
        self._create_capsule_file(settings, "Tech", "test1")

        result = load_capsules(settings)

        assert len(result) == 1
        assert result[0]["id"] == "test1"
        assert result[0]["title"] == "Title for test1"

    def test_loads_multiple_capsules(self, settings):
        """Test loading multiple capsules."""
        self._create_capsule_file(settings, "Tech", "capsule1")
        self._create_capsule_file(settings, "Science", "capsule2")
        self._create_capsule_file(settings, "Tech", "capsule3")

        result = load_capsules(settings)

        assert len(result) == 3

    def test_sorted_by_captured_at_newest_first(self, settings):
        """Test that capsules are sorted by date, newest first."""
        self._create_capsule_file(settings, "Tech", "old", captured_at="2024-01-01")
        self._create_capsule_file(settings, "Tech", "new", captured_at="2024-01-20")
        self._create_capsule_file(settings, "Tech", "mid", captured_at="2024-01-10")

        result = load_capsules(settings)

        assert result[0]["id"] == "new"
        assert result[1]["id"] == "mid"
        assert result[2]["id"] == "old"

    def test_excludes_legacy_by_default(self, settings):
        """Test that legacy capsules are excluded by default."""
        self._create_capsule_file(settings, "Tech", "active1")
        self._create_capsule_file(settings, "Tech", "legacy1", status="legacy")

        result = load_capsules(settings)

        assert len(result) == 1
        assert result[0]["id"] == "active1"

    def test_includes_legacy_when_requested(self, settings):
        """Test that legacy capsules can be included."""
        self._create_capsule_file(settings, "Tech", "active1")
        self._create_capsule_file(settings, "Tech", "legacy1", status="legacy")

        result = load_capsules(settings, include_legacy=True)

        assert len(result) == 2

    def test_adds_path_metadata(self, settings):
        """Test that path metadata is added to capsules."""
        self._create_capsule_file(settings, "Tech", "test1")

        result = load_capsules(settings)

        assert "_path" in result[0]
        assert "_filename" in result[0]
        assert "_absolute_path" in result[0]
        assert result[0]["_filename"] == "test1.md"

    def test_includes_content_when_requested(self, settings):
        """Test that content can be included."""
        self._create_capsule_file(settings, "Tech", "test1")

        result = load_capsules(settings, include_content=True)

        assert "_content" in result[0]
        assert "Test summary for test1" in result[0]["_content"]

    def test_excludes_content_by_default(self, settings):
        """Test that content is excluded by default."""
        self._create_capsule_file(settings, "Tech", "test1")

        result = load_capsules(settings, include_content=False)

        assert "_content" not in result[0]

    def test_skips_files_with_parse_errors(self, settings):
        """Test that files with YAML parse errors are skipped."""
        # Create valid capsule
        self._create_capsule_file(settings, "Tech", "valid")

        # Create file with malformed YAML frontmatter (should cause parse error)
        invalid_path = settings.capsules_path / "Tech" / "invalid.md"
        invalid_path.write_text("---\n[invalid: yaml: content\n---\nContent", encoding="utf-8")

        result = load_capsules(settings)

        # Should only have the valid one
        assert len(result) == 1
        assert result[0]["id"] == "valid"


class TestFindCapsuleFile:
    """Tests for find_capsule_file function."""

    def test_finds_existing_file(self, settings):
        """Test finding an existing capsule file."""
        category_dir = settings.capsules_path / "Tech"
        category_dir.mkdir(parents=True)
        capsule_path = category_dir / "test_capsule.md"
        capsule_path.write_text("---\nid: test\n---\nContent")

        result = find_capsule_file(settings, "test_capsule.md")

        assert result == capsule_path

    def test_returns_none_for_nonexistent(self, settings):
        """Test that None is returned for nonexistent file."""
        result = find_capsule_file(settings, "does_not_exist.md")

        assert result is None

    def test_finds_in_nested_categories(self, settings):
        """Test finding file in nested category structure."""
        nested_dir = settings.capsules_path / "Tech" / "Python"
        nested_dir.mkdir(parents=True)
        capsule_path = nested_dir / "nested.md"
        capsule_path.write_text("content")

        result = find_capsule_file(settings, "nested.md")

        assert result == capsule_path

    def test_finds_first_match(self, settings):
        """Test that search returns a match (behavior with duplicates)."""
        dir1 = settings.capsules_path / "Cat1"
        dir2 = settings.capsules_path / "Cat2"
        dir1.mkdir(parents=True)
        dir2.mkdir(parents=True)

        (dir1 / "same.md").write_text("content1")
        (dir2 / "same.md").write_text("content2")

        result = find_capsule_file(settings, "same.md")

        # Should find one of them
        assert result is not None
        assert result.name == "same.md"
