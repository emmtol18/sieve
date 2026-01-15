"""Tests for sieve.capsule.schema module."""

from datetime import date

import pytest
import yaml

from sieve.capsule.schema import Capsule, CapsuleInput, CapsuleMetadata


class TestCapsuleMetadata:
    """Tests for CapsuleMetadata model."""

    def test_minimal_metadata(self):
        """Test creating metadata with minimal required fields."""
        meta = CapsuleMetadata(
            id="2024-01-15-T100000",
            title="Test Title",
        )

        assert meta.id == "2024-01-15-T100000"
        assert meta.title == "Test Title"
        assert meta.source_url is None
        assert meta.tags == []
        assert meta.category == "Uncategorized"
        assert meta.status == "active"
        assert meta.pinned is False
        assert meta.capture_method == "manual"
        assert meta.original_asset is None

    def test_full_metadata(self, sample_metadata):
        """Test creating metadata with all fields."""
        meta = sample_metadata

        assert meta.id == "2024-01-15-T100000-123456"
        assert meta.title == "Test Capsule Title"
        assert meta.source_url == "https://example.com/article"
        assert meta.tags == ["testing", "python"]
        assert meta.category == "Technology"
        assert meta.status == "active"
        assert meta.pinned is False
        assert meta.captured_at == date(2024, 1, 15)
        assert meta.capture_method == "manual"

    def test_to_frontmatter(self, sample_metadata):
        """Test conversion to YAML-serializable dict."""
        frontmatter = sample_metadata.to_frontmatter()

        assert frontmatter["id"] == "2024-01-15-T100000-123456"
        assert frontmatter["title"] == "Test Capsule Title"
        assert frontmatter["source_url"] == "https://example.com/article"
        assert frontmatter["tags"] == ["testing", "python"]
        assert frontmatter["category"] == "Technology"
        assert frontmatter["captured_at"] == "2024-01-15"  # ISO format string

    def test_captured_at_defaults_to_today(self):
        """Test that captured_at defaults to today's date."""
        meta = CapsuleMetadata(
            id="test-id",
            title="Test",
        )

        assert meta.captured_at == date.today()


class TestCapsule:
    """Tests for Capsule model."""

    def test_capsule_creation(self, sample_capsule):
        """Test creating a complete capsule."""
        capsule = sample_capsule

        assert capsule.metadata.title == "Test Capsule Title"
        assert "test capsule" in capsule.executive_summary.lower()
        assert "Unit tests" in capsule.core_insight
        assert "multiple paragraphs" in capsule.full_content

    def test_filename_generation(self, sample_capsule):
        """Test that filename is generated correctly."""
        filename = sample_capsule.filename

        assert filename.startswith("20240115_")
        assert filename.endswith(".md")
        assert "test" in filename.lower()
        assert "capsule" in filename.lower()

    def test_filename_handles_special_characters(self):
        """Test filename generation with special characters in title."""
        meta = CapsuleMetadata(
            id="test",
            title="Test: A 'Special' Title! With @#$ Characters",
            captured_at=date(2024, 1, 15),
        )
        capsule = Capsule(
            metadata=meta,
            executive_summary="Summary",
            core_insight="Insight",
            full_content="Content",
        )

        filename = capsule.filename

        # After removing special chars, we get: "Test A Special Title With  Characters"
        # First 6 words: test, a, special, title, with, characters
        assert filename == "20240115_test_a_special_title_with_characters.md"
        # No special chars in filename
        assert ":" not in filename
        assert "!" not in filename
        assert "@" not in filename

    def test_filename_limits_words(self):
        """Test that filename is limited to first 6 words."""
        meta = CapsuleMetadata(
            id="test",
            title="One Two Three Four Five Six Seven Eight Nine Ten",
            captured_at=date(2024, 1, 15),
        )
        capsule = Capsule(
            metadata=meta,
            executive_summary="Summary",
            core_insight="Insight",
            full_content="Content",
        )

        filename = capsule.filename

        assert filename == "20240115_one_two_three_four_five_six.md"

    def test_to_markdown(self, sample_capsule):
        """Test conversion to markdown with frontmatter."""
        markdown = sample_capsule.to_markdown()

        # Check frontmatter delimiters
        assert markdown.startswith("---\n")
        assert "\n---\n" in markdown

        # Check sections exist
        assert "# Executive Summary" in markdown
        assert "# Core Insight" in markdown
        assert "# Full Content" in markdown

        # Check content is included
        assert sample_capsule.executive_summary in markdown
        assert sample_capsule.core_insight in markdown
        assert sample_capsule.full_content in markdown

    def test_to_markdown_frontmatter_is_valid_yaml(self, sample_capsule):
        """Test that frontmatter section is valid YAML."""
        markdown = sample_capsule.to_markdown()

        # Extract frontmatter between --- markers
        parts = markdown.split("---")
        frontmatter_yaml = parts[1].strip()

        # Should parse without error
        data = yaml.safe_load(frontmatter_yaml)

        assert data["id"] == sample_capsule.metadata.id
        assert data["title"] == sample_capsule.metadata.title
        assert data["tags"] == sample_capsule.metadata.tags


class TestCapsuleInput:
    """Tests for CapsuleInput model."""

    def test_minimal_input(self):
        """Test creating input with minimal fields."""
        input_data = CapsuleInput(content="Test content")

        assert input_data.content == "Test content"
        assert input_data.source_url is None
        assert input_data.title is None
        assert input_data.tags == []
        assert input_data.notes is None
        assert input_data.capture_method == "manual"
        assert input_data.image_data is None

    def test_full_input(self):
        """Test creating input with all fields."""
        input_data = CapsuleInput(
            content="Full content",
            source_url="https://example.com",
            title="Input Title",
            tags=["tag1", "tag2"],
            notes="Some notes",
            capture_method="browser",
            image_data="base64data==",
        )

        assert input_data.content == "Full content"
        assert input_data.source_url == "https://example.com"
        assert input_data.title == "Input Title"
        assert input_data.tags == ["tag1", "tag2"]
        assert input_data.notes == "Some notes"
        assert input_data.capture_method == "browser"
        assert input_data.image_data == "base64data=="
