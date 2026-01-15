"""Tests for sieve.utils module."""

from pathlib import Path

import pytest

from sieve.utils import get_unique_path


class TestGetUniquePath:
    """Tests for get_unique_path function."""

    def test_returns_original_if_not_exists(self, tmp_path):
        """Test that original path is returned if file doesn't exist."""
        path = tmp_path / "test_file.txt"

        result = get_unique_path(path)

        assert result == path

    def test_adds_counter_if_exists(self, tmp_path):
        """Test that counter is added when file exists."""
        path = tmp_path / "test_file.txt"
        path.touch()

        result = get_unique_path(path)

        assert result == tmp_path / "test_file_1.txt"

    def test_increments_counter_for_multiple_conflicts(self, tmp_path):
        """Test that counter increments correctly."""
        base_path = tmp_path / "test_file.txt"
        base_path.touch()
        (tmp_path / "test_file_1.txt").touch()
        (tmp_path / "test_file_2.txt").touch()

        result = get_unique_path(base_path)

        assert result == tmp_path / "test_file_3.txt"

    def test_preserves_file_extension(self, tmp_path):
        """Test that file extension is preserved correctly."""
        path = tmp_path / "image.png"
        path.touch()

        result = get_unique_path(path)

        assert result.suffix == ".png"
        assert result.stem == "image_1"

    def test_works_with_directories(self, tmp_path):
        """Test that function works with existing directories too."""
        dir_path = tmp_path / "my_folder"
        dir_path.mkdir()

        result = get_unique_path(dir_path)

        assert result == tmp_path / "my_folder_1"

    def test_handles_no_extension(self, tmp_path):
        """Test that files without extensions are handled."""
        path = tmp_path / "Makefile"
        path.touch()

        result = get_unique_path(path)

        assert result == tmp_path / "Makefile_1"

    def test_handles_dotfiles(self, tmp_path):
        """Test that dotfiles are handled correctly."""
        path = tmp_path / ".gitignore"
        path.touch()

        result = get_unique_path(path)

        # Path handles dotfiles as: stem=".gitignore", suffix=""
        # So the result is ".gitignore_1" (no extension)
        assert result == tmp_path / ".gitignore_1"

    def test_handles_multiple_dots_in_name(self, tmp_path):
        """Test files with multiple dots in the name."""
        path = tmp_path / "archive.tar.gz"
        path.touch()

        result = get_unique_path(path)

        assert result == tmp_path / "archive.tar_1.gz"
