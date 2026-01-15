"""Tests for sieve.capsule.writer module."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from sieve.capsule.schema import Capsule, CapsuleMetadata
from sieve.capsule.writer import CapsuleWriter


class TestCapsuleWriter:
    """Tests for CapsuleWriter class."""

    @pytest.fixture
    def writer(self, settings):
        """Create a CapsuleWriter instance."""
        return CapsuleWriter(settings)

    @pytest.fixture
    def simple_capsule(self):
        """Create a simple capsule for testing."""
        meta = CapsuleMetadata(
            id="test-id",
            title="Simple Test",
            category="Testing",
            captured_at=date(2024, 1, 15),
        )
        return Capsule(
            metadata=meta,
            executive_summary="Test summary",
            core_insight="Test insight",
            full_content="Test content",
        )

    def test_write_creates_category_directory(self, writer, simple_capsule, settings):
        """Test that write creates the category directory."""
        writer.write(simple_capsule)

        category_dir = settings.capsules_path / "Testing"
        assert category_dir.exists()

    def test_write_creates_capsule_file(self, writer, simple_capsule, settings):
        """Test that write creates the capsule markdown file."""
        path = writer.write(simple_capsule)

        assert path.exists()
        assert path.suffix == ".md"
        assert path.parent.name == "Testing"

    def test_write_content_is_correct(self, writer, simple_capsule):
        """Test that written file contains correct content."""
        path = writer.write(simple_capsule)

        content = path.read_text(encoding="utf-8")

        assert "Test summary" in content
        assert "Test insight" in content
        assert "Test content" in content
        assert "Simple Test" in content

    def test_write_with_original_file(self, writer, simple_capsule, settings, tmp_path):
        """Test that original file is copied to assets."""
        # Create a source file
        source_file = tmp_path / "original.txt"
        source_file.write_text("Original content")

        with patch("sieve.capsule.writer.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15)
            path = writer.write(simple_capsule, original_file=source_file)

        # Check asset was copied
        assets_dir = settings.assets_path / "2024-01"
        assert assets_dir.exists()
        asset_files = list(assets_dir.glob("original*.txt"))
        assert len(asset_files) == 1

    def test_write_updates_original_asset_path(self, writer, simple_capsule, tmp_path):
        """Test that original_asset metadata is updated after copy."""
        source_file = tmp_path / "original.png"
        source_file.write_bytes(b"fake image data")

        with patch("sieve.capsule.writer.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15)
            path = writer.write(simple_capsule, original_file=source_file)

        content = path.read_text(encoding="utf-8")
        assert "original_asset:" in content
        assert "Assets/2024-01" in content

    def test_write_handles_missing_original_file(self, writer, simple_capsule, tmp_path):
        """Test that missing original file is handled gracefully."""
        nonexistent = tmp_path / "does_not_exist.txt"

        # Should not raise an error
        path = writer.write(simple_capsule, original_file=nonexistent)

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "original_asset: null" in content or "original_asset:" not in content


class TestCapsuleWriterAssetHandling:
    """Tests for asset copying functionality."""

    @pytest.fixture
    def writer(self, settings):
        """Create a CapsuleWriter instance."""
        return CapsuleWriter(settings)

    def test_copy_asset_creates_month_directory(self, writer, settings, tmp_path):
        """Test that assets are organized by month."""
        source = tmp_path / "test.png"
        source.write_bytes(b"test data")

        with patch("sieve.capsule.writer.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 6, 20)
            dest = writer._copy_asset(source)

        assert dest.parent == settings.assets_path / "2024-06"

    def test_copy_asset_handles_name_conflicts(self, writer, settings, tmp_path):
        """Test that duplicate asset names are handled."""
        source = tmp_path / "image.png"
        source.write_bytes(b"test data")

        with patch("sieve.capsule.writer.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15)

            # Create first copy
            dest1 = writer._copy_asset(source)
            # Create second copy
            dest2 = writer._copy_asset(source)

        assert dest1 != dest2
        assert dest1.name == "image.png"
        assert dest2.name == "image_1.png"


class TestMoveToLegacy:
    """Tests for move_to_legacy functionality."""

    @pytest.fixture
    def writer(self, settings):
        """Create a CapsuleWriter instance."""
        return CapsuleWriter(settings)

    def test_move_to_legacy_creates_legacy_dir(self, writer, settings):
        """Test that Legacy directory is created if needed."""
        capsule_path = settings.capsules_path / "Test" / "test.md"
        capsule_path.parent.mkdir(parents=True)
        capsule_path.write_text("test content")

        writer.move_to_legacy(capsule_path)

        assert settings.legacy_path.exists()

    def test_move_to_legacy_moves_file(self, writer, settings):
        """Test that file is moved to Legacy folder."""
        capsule_path = settings.capsules_path / "Test" / "test.md"
        capsule_path.parent.mkdir(parents=True)
        capsule_path.write_text("test content")

        result = writer.move_to_legacy(capsule_path)

        assert not capsule_path.exists()
        assert result.exists()
        assert result.parent == settings.legacy_path

    def test_move_to_legacy_handles_conflicts(self, writer, settings):
        """Test that conflicting names in Legacy are handled."""
        capsule_path = settings.capsules_path / "Test" / "test.md"
        capsule_path.parent.mkdir(parents=True)
        capsule_path.write_text("original")

        # Create existing file in Legacy
        settings.legacy_path.mkdir(exist_ok=True)
        (settings.legacy_path / "test.md").write_text("existing")

        result = writer.move_to_legacy(capsule_path)

        assert result.name == "test_1.md"
