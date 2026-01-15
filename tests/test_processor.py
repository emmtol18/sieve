"""Tests for sieve.engine.processor module."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sieve.capsule.schema import Capsule, CapsuleMetadata
from sieve.engine.processor import Processor


class TestProcessor:
    """Tests for Processor class."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM client."""
        return MagicMock()

    @pytest.fixture
    def processor(self, settings, mock_llm):
        """Create a Processor instance with mocked LLM."""
        proc = Processor(settings)
        proc.llm = mock_llm
        return proc

    @pytest.fixture
    def sample_capsule_result(self):
        """Create a sample capsule that LLM would return."""
        meta = CapsuleMetadata(
            id="2024-01-15-T100000",
            title="Processed Article",
            category="Technology",
            captured_at=date(2024, 1, 15),
        )
        return Capsule(
            metadata=meta,
            executive_summary="Summary from LLM",
            core_insight="Insight from LLM",
            full_content="Content from LLM",
        )

    def test_get_extractor_for_html(self, processor, tmp_path):
        """Test that HTML files get HTMLExtractor."""
        html_file = tmp_path / "test.html"
        html_file.write_text("<html><body>Test</body></html>")

        extractor = processor._get_extractor(html_file)

        assert extractor is not None
        assert extractor.__class__.__name__ == "HTMLExtractor"

    def test_get_extractor_for_text(self, processor, tmp_path):
        """Test that text files get TextExtractor."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Test content")

        extractor = processor._get_extractor(txt_file)

        assert extractor is not None
        assert extractor.__class__.__name__ == "TextExtractor"

    def test_get_extractor_for_image(self, processor, tmp_path):
        """Test that image files get ImageExtractor."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake png")

        extractor = processor._get_extractor(img_file)

        assert extractor is not None
        assert extractor.__class__.__name__ == "ImageExtractor"

    def test_get_extractor_returns_none_for_unknown(self, processor, tmp_path):
        """Test that unknown files return None."""
        unknown_file = tmp_path / "test.xyz"
        unknown_file.write_text("unknown")

        extractor = processor._get_extractor(unknown_file)

        assert extractor is None

    async def test_process_file_text_success(self, processor, settings, sample_capsule_result):
        """Test successful processing of a text file."""
        # Create test file in inbox
        txt_file = settings.inbox_path / "test_article.txt"
        txt_file.write_text("# Test Article\n\nSome content here.")

        # Mock LLM response
        processor.llm.process_text = AsyncMock(return_value=sample_capsule_result)

        # Mock indexer
        processor.indexer.regenerate = AsyncMock()

        result = await processor.process_file(txt_file)

        assert result is not None
        assert result.exists()
        processor.llm.process_text.assert_called_once()
        processor.indexer.regenerate.assert_called_once()

    async def test_process_file_removes_source(self, processor, settings, sample_capsule_result):
        """Test that source file is removed after processing."""
        txt_file = settings.inbox_path / "to_delete.txt"
        txt_file.write_text("Content to process")

        processor.llm.process_text = AsyncMock(return_value=sample_capsule_result)
        processor.indexer.regenerate = AsyncMock()

        await processor.process_file(txt_file)

        assert not txt_file.exists()

    async def test_process_file_image_uses_vision(self, processor, settings, sample_capsule_result):
        """Test that images are processed with vision API."""
        img_file = settings.inbox_path / "screenshot.png"
        img_file.write_bytes(b"fake png data")

        processor.llm.process_image = AsyncMock(return_value=sample_capsule_result)
        processor.indexer.regenerate = AsyncMock()

        await processor.process_file(img_file, capture_method="screenshot")

        processor.llm.process_image.assert_called_once()
        call_args = processor.llm.process_image.call_args
        assert call_args[0][0] == img_file
        assert call_args[1]["capture_method"] == "screenshot"

    async def test_process_file_unsupported_returns_none(self, processor, settings):
        """Test that unsupported files return None."""
        unknown_file = settings.inbox_path / "test.xyz"
        unknown_file.write_text("unknown content")

        result = await processor.process_file(unknown_file)

        assert result is None

    async def test_process_file_error_handling(self, processor, settings):
        """Test error handling during processing."""
        txt_file = settings.inbox_path / "error.txt"
        txt_file.write_text("Content")

        processor.llm.process_text = AsyncMock(side_effect=Exception("API Error"))

        result = await processor.process_file(txt_file)

        assert result is None
        # File should still exist since processing failed
        assert txt_file.exists()

    async def test_process_file_increments_error_count(self, processor, settings):
        """Test that error count is tracked."""
        txt_file = settings.inbox_path / "error.txt"
        txt_file.write_text("Content")

        processor.llm.process_text = AsyncMock(side_effect=Exception("API Error"))

        # Process multiple times
        await processor.process_file(txt_file)
        await processor.process_file(txt_file)

        assert str(txt_file) in processor._error_counts
        assert processor._error_counts[str(txt_file)] == 2

    async def test_process_file_moves_to_failed_after_max_retries(self, processor, settings):
        """Test that file is moved to failed folder after max retries."""
        txt_file = settings.inbox_path / "persistent_error.txt"
        txt_file.write_text("Content that always fails")

        processor.llm.process_text = AsyncMock(side_effect=Exception("API Error"))
        settings.max_retries = 3

        # Process until max retries
        for _ in range(3):
            await processor.process_file(txt_file)

        # File should be in failed folder
        failed_file = settings.failed_path / "persistent_error.txt"
        assert failed_file.exists()
        assert not txt_file.exists()

    async def test_process_file_clears_error_count_on_success(
        self, processor, settings, sample_capsule_result
    ):
        """Test that error count is cleared after success."""
        txt_file = settings.inbox_path / "recover.txt"
        txt_file.write_text("Content")

        # First call fails
        processor.llm.process_text = AsyncMock(side_effect=Exception("Error"))
        await processor.process_file(txt_file)

        assert str(txt_file) in processor._error_counts

        # Second call succeeds
        processor.llm.process_text = AsyncMock(return_value=sample_capsule_result)
        processor.indexer.regenerate = AsyncMock()
        await processor.process_file(txt_file)

        assert str(txt_file) not in processor._error_counts

    async def test_log_error_creates_log_file(self, processor, settings):
        """Test that errors are logged to file."""
        test_path = settings.inbox_path / "error.txt"
        test_error = Exception("Test error message")

        processor._log_error(test_path, test_error)

        assert settings.error_log_path.exists()
        log_content = settings.error_log_path.read_text()
        assert "error.txt" in log_content
        assert "Test error message" in log_content


class TestProcessBrowserCapture:
    """Tests for browser capture processing."""

    @pytest.fixture
    def processor(self, settings):
        """Create a Processor instance."""
        proc = Processor(settings)
        proc.llm = MagicMock()
        proc.indexer = MagicMock()
        return proc

    @pytest.fixture
    def sample_capsule(self):
        """Create a sample capsule."""
        meta = CapsuleMetadata(
            id="browser-capture",
            title="Browser Captured",
            category="Web",
            captured_at=date(2024, 1, 15),
        )
        return Capsule(
            metadata=meta,
            executive_summary="Browser summary",
            core_insight="Browser insight",
            full_content="Browser content",
        )

    async def test_process_browser_text_capture(self, processor, sample_capsule):
        """Test processing text from browser extension."""
        processor.llm.process_text = AsyncMock(return_value=sample_capsule)
        processor.indexer.regenerate = AsyncMock()

        result = await processor.process_browser_capture(
            content="Selected text from browser",
            source_url="https://example.com/article",
        )

        assert result.exists()
        processor.llm.process_text.assert_called_once_with(
            "Selected text from browser",
            source_url="https://example.com/article",
            capture_method="browser",
        )

    async def test_process_browser_image_capture(self, processor, sample_capsule):
        """Test processing image from browser extension."""
        processor.llm.process_image_base64 = AsyncMock(return_value=sample_capsule)
        processor.indexer.regenerate = AsyncMock()

        result = await processor.process_browser_capture(
            content="",
            source_url="https://example.com",
            image_data="base64encodedimage==",
        )

        assert result.exists()
        processor.llm.process_image_base64.assert_called_once_with(
            "base64encodedimage==",
            source_url="https://example.com",
            capture_method="browser",
        )

    async def test_process_browser_updates_index(self, processor, sample_capsule):
        """Test that browser capture updates the index."""
        processor.llm.process_text = AsyncMock(return_value=sample_capsule)
        processor.indexer.regenerate = AsyncMock()

        await processor.process_browser_capture(content="Test")

        processor.indexer.regenerate.assert_called_once()
