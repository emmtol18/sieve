"""Tests for sieve.engine.extractors module."""

import json
from pathlib import Path

import pytest

from sieve.engine.extractors import HTMLExtractor, ImageExtractor, TextExtractor
from sieve.engine.extractors.base import ExtractedContent, Extractor


class TestExtractedContent:
    """Tests for ExtractedContent dataclass."""

    def test_default_values(self):
        """Test default values for ExtractedContent."""
        content = ExtractedContent()

        assert content.text is None
        assert content.is_image is False
        assert content.image_path is None
        assert content.source_url is None
        assert content.suggested_title is None

    def test_text_content(self):
        """Test creating text content."""
        content = ExtractedContent(
            text="Sample text content",
            source_url="https://example.com",
            suggested_title="Sample Title",
        )

        assert content.text == "Sample text content"
        assert content.is_image is False
        assert content.source_url == "https://example.com"

    def test_image_content(self):
        """Test creating image content."""
        content = ExtractedContent(
            is_image=True,
            image_path=Path("/tmp/image.png"),
        )

        assert content.is_image is True
        assert content.image_path == Path("/tmp/image.png")


class TestHTMLExtractor:
    """Tests for HTMLExtractor class."""

    @pytest.fixture
    def extractor(self):
        return HTMLExtractor()

    def test_can_handle_html(self, extractor):
        """Test that HTML files are handled."""
        assert extractor.can_handle(Path("test.html")) is True
        assert extractor.can_handle(Path("test.htm")) is True
        assert extractor.can_handle(Path("test.HTML")) is True

    def test_cannot_handle_other_files(self, extractor):
        """Test that non-HTML files are rejected."""
        assert extractor.can_handle(Path("test.txt")) is False
        assert extractor.can_handle(Path("test.md")) is False
        assert extractor.can_handle(Path("test.png")) is False

    def test_extract_basic_html(self, extractor, tmp_path, sample_html):
        """Test extracting content from basic HTML."""
        html_file = tmp_path / "test.html"
        html_file.write_text(sample_html)

        result = extractor.extract(html_file)

        assert result.is_image is False
        assert "Main Heading" in result.text
        assert "main article content" in result.text
        assert "multiple paragraphs" in result.text

    def test_extract_removes_nav_elements(self, extractor, tmp_path, sample_html):
        """Test that navigation elements are removed."""
        html_file = tmp_path / "test.html"
        html_file.write_text(sample_html)

        result = extractor.extract(html_file)

        assert "Navigation to skip" not in result.text

    def test_extract_removes_footer(self, extractor, tmp_path, sample_html):
        """Test that footer is removed."""
        html_file = tmp_path / "test.html"
        html_file.write_text(sample_html)

        result = extractor.extract(html_file)

        assert "Footer to skip" not in result.text

    def test_extract_title(self, extractor, tmp_path, sample_html):
        """Test that title is extracted."""
        html_file = tmp_path / "test.html"
        html_file.write_text(sample_html)

        result = extractor.extract(html_file)

        assert result.suggested_title == "Sample Article Title"

    def test_extract_canonical_url(self, extractor, tmp_path, sample_html):
        """Test that canonical URL is extracted."""
        html_file = tmp_path / "test.html"
        html_file.write_text(sample_html)

        result = extractor.extract(html_file)

        assert result.source_url == "https://example.com/canonical-url"

    def test_extract_og_url_fallback(self, extractor, tmp_path):
        """Test that og:url is used as fallback."""
        html = """
        <html>
        <head>
            <meta property="og:url" content="https://example.com/og-url">
        </head>
        <body><p>Content</p></body>
        </html>
        """
        html_file = tmp_path / "test.html"
        html_file.write_text(html)

        result = extractor.extract(html_file)

        assert result.source_url == "https://example.com/og-url"

    def test_extract_handles_no_article(self, extractor, tmp_path):
        """Test extraction when there's no article tag."""
        html = """
        <html>
        <body>
            <p>Just a paragraph</p>
        </body>
        </html>
        """
        html_file = tmp_path / "test.html"
        html_file.write_text(html)

        result = extractor.extract(html_file)

        assert "Just a paragraph" in result.text


class TestTextExtractor:
    """Tests for TextExtractor class."""

    @pytest.fixture
    def extractor(self):
        return TextExtractor()

    def test_can_handle_text_files(self, extractor):
        """Test that text files are handled."""
        assert extractor.can_handle(Path("test.txt")) is True
        assert extractor.can_handle(Path("test.md")) is True
        assert extractor.can_handle(Path("test.markdown")) is True
        assert extractor.can_handle(Path("test.rst")) is True
        assert extractor.can_handle(Path("test.json")) is True

    def test_cannot_handle_other_files(self, extractor):
        """Test that non-text files are rejected."""
        assert extractor.can_handle(Path("test.html")) is False
        assert extractor.can_handle(Path("test.png")) is False
        assert extractor.can_handle(Path("test.py")) is False

    def test_extract_plain_text(self, extractor, tmp_path):
        """Test extracting plain text content."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world\nThis is content")

        result = extractor.extract(txt_file)

        assert result.text == "Hello world\nThis is content"
        assert result.is_image is False

    def test_extract_markdown_title(self, extractor, tmp_path, sample_markdown):
        """Test extracting title from markdown."""
        md_file = tmp_path / "test.md"
        md_file.write_text(sample_markdown)

        result = extractor.extract(md_file)

        assert result.suggested_title == "Main Title"

    def test_extract_h2_title_fallback(self, extractor, tmp_path):
        """Test using h2 as title fallback."""
        md_content = "## Section Title\n\nContent here"
        md_file = tmp_path / "test.md"
        md_file.write_text(md_content)

        result = extractor.extract(md_file)

        assert result.suggested_title == "Section Title"

    def test_extract_title_from_filename(self, extractor, tmp_path):
        """Test falling back to filename for title."""
        txt_file = tmp_path / "my_document_title.txt"
        txt_file.write_text("No heading here")

        result = extractor.extract(txt_file)

        assert result.suggested_title == "My Document Title"

    def test_extract_json_browser_format(self, extractor, tmp_path, sample_json_capture):
        """Test extracting browser extension JSON format."""
        json_file = tmp_path / "capture.json"
        json_file.write_text(sample_json_capture)

        result = extractor.extract(json_file)

        assert result.text == "Captured content from browser"
        assert result.source_url == "https://example.com/page"
        assert result.suggested_title == "Browser Captured Title"

    def test_extract_json_with_url_key(self, extractor, tmp_path):
        """Test JSON with 'url' instead of 'source_url'."""
        json_data = json.dumps({
            "content": "Content",
            "url": "https://example.com/url-key",
        })
        json_file = tmp_path / "capture.json"
        json_file.write_text(json_data)

        result = extractor.extract(json_file)

        assert result.source_url == "https://example.com/url-key"

    def test_extract_json_fallback_to_dump(self, extractor, tmp_path):
        """Test JSON without content key falls back to dump."""
        json_data = json.dumps({"key": "value", "other": 123})
        json_file = tmp_path / "data.json"
        json_file.write_text(json_data)

        result = extractor.extract(json_file)

        assert '"key": "value"' in result.text

    def test_extract_invalid_json_returns_raw(self, extractor, tmp_path):
        """Test that invalid JSON returns raw content."""
        json_file = tmp_path / "bad.json"
        json_file.write_text("{not valid json")

        result = extractor.extract(json_file)

        assert result.text == "{not valid json"


class TestImageExtractor:
    """Tests for ImageExtractor class."""

    @pytest.fixture
    def extractor(self):
        return ImageExtractor()

    def test_can_handle_images(self, extractor):
        """Test that image files are handled."""
        assert extractor.can_handle(Path("test.png")) is True
        assert extractor.can_handle(Path("test.jpg")) is True
        assert extractor.can_handle(Path("test.jpeg")) is True
        assert extractor.can_handle(Path("test.gif")) is True
        assert extractor.can_handle(Path("test.webp")) is True
        assert extractor.can_handle(Path("test.bmp")) is True
        assert extractor.can_handle(Path("test.tiff")) is True

    def test_handles_uppercase_extensions(self, extractor):
        """Test that uppercase extensions work."""
        assert extractor.can_handle(Path("test.PNG")) is True
        assert extractor.can_handle(Path("test.JPG")) is True

    def test_cannot_handle_non_images(self, extractor):
        """Test that non-image files are rejected."""
        assert extractor.can_handle(Path("test.txt")) is False
        assert extractor.can_handle(Path("test.html")) is False
        assert extractor.can_handle(Path("test.pdf")) is False

    def test_extract_returns_image_content(self, extractor, tmp_path):
        """Test that extraction returns image content."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # PNG header

        result = extractor.extract(img_file)

        assert result.is_image is True
        assert result.image_path == img_file
        assert result.text is None

    def test_extract_generates_title_from_filename(self, extractor, tmp_path):
        """Test that title is generated from filename."""
        img_file = tmp_path / "my_screenshot_2024.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        result = extractor.extract(img_file)

        assert result.suggested_title == "My Screenshot 2024"

    def test_extract_handles_hyphen_in_filename(self, extractor, tmp_path):
        """Test filename with hyphens."""
        img_file = tmp_path / "screen-shot-example.jpg"
        img_file.write_bytes(b"fake jpg")

        result = extractor.extract(img_file)

        assert result.suggested_title == "Screen Shot Example"
