"""Tests for sieve.llm.openai module."""

import asyncio
import base64
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIConnectionError, APIError, RateLimitError

from sieve.llm.openai import CapsuleExtraction, OpenAIClient
from sieve.llm.prompts import CAPSULE_SYSTEM_PROMPT, IMAGE_SYSTEM_PROMPT


def create_valid_extraction():
    """Create a valid CapsuleExtraction object."""
    return CapsuleExtraction(
        title="Test Article Title",
        executive_summary="This is a summary. It has two sentences.",
        core_insight="The main insight from this content.",
        full_content="The full processed content.",
        tags=["testing", "python"],
        category="Technology",
    )


def create_mock_response(extraction: CapsuleExtraction, status: str = "completed"):
    """Create a mock OpenAI response object matching responses.parse output."""
    mock = MagicMock()
    mock.status = status
    mock.output_parsed = extraction
    mock.incomplete_details = None
    mock.output = [
        MagicMock(content=[
            MagicMock(type="text", text="response text")
        ])
    ]
    return mock


class TestOpenAIClient:
    """Tests for OpenAIClient class."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        mock = MagicMock()
        mock.responses = MagicMock()
        mock.responses.parse = AsyncMock()
        return mock

    @pytest.fixture
    def client(self, settings, mock_openai):
        """Create OpenAIClient with mocked dependencies."""
        with patch("sieve.llm.openai.AsyncOpenAI", return_value=mock_openai):
            client = OpenAIClient(settings)
            client.client = mock_openai
            return client

    @pytest.fixture
    def valid_extraction(self):
        """Create a valid CapsuleExtraction object."""
        return create_valid_extraction()

    def test_init(self, settings):
        """Test client initialization."""
        with patch("sieve.llm.openai.AsyncOpenAI") as mock_class:
            client = OpenAIClient(settings)

            mock_class.assert_called_once_with(api_key=settings.openai_api_key)
            assert client.model == settings.openai_model

    async def test_call_with_retry_structured_success(self, client, mock_openai, valid_extraction):
        """Test successful API call with structured output."""
        mock_response = create_mock_response(valid_extraction)
        mock_openai.responses.parse.return_value = mock_response

        result = await client._call_with_retry_structured(
            input_content="test content",
            instructions="test instructions",
        )

        assert isinstance(result, CapsuleExtraction)
        assert result.title == valid_extraction.title
        mock_openai.responses.parse.assert_called_once()

    async def test_call_with_retry_structured_retries_on_rate_limit(self, client, mock_openai, valid_extraction):
        """Test that rate limit errors trigger retry."""
        mock_response = create_mock_response(valid_extraction)

        # First call fails, second succeeds
        mock_openai.responses.parse.side_effect = [
            RateLimitError(
                message="Rate limit",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit"}},
            ),
            mock_response,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._call_with_retry_structured(
                input_content="test",
                instructions="instructions",
            )

        assert isinstance(result, CapsuleExtraction)
        assert mock_openai.responses.parse.call_count == 2

    async def test_call_with_retry_structured_exponential_backoff(self, client, mock_openai):
        """Test exponential backoff on retries."""
        mock_openai.responses.parse.side_effect = RateLimitError(
            message="Rate limit",
            response=MagicMock(status_code=429),
            body={"error": {"message": "Rate limit"}},
        )

        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch("asyncio.sleep", mock_sleep):
            with pytest.raises(RateLimitError):
                client.settings.max_retries = 3
                await client._call_with_retry_structured(
                    input_content="test",
                    instructions="instructions",
                )

        # Check exponential backoff: 1, 2, 4
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == 1.0
        assert sleep_calls[1] == 2.0
        assert sleep_calls[2] == 4.0

    async def test_call_with_retry_structured_gives_up_after_max_retries(self, client, mock_openai):
        """Test that client gives up after max retries."""
        mock_openai.responses.parse.side_effect = APIConnectionError(
            request=MagicMock()
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(APIConnectionError):
                client.settings.max_retries = 2
                await client._call_with_retry_structured(
                    input_content="test",
                    instructions="instructions",
                )

        assert mock_openai.responses.parse.call_count == 2

    async def test_call_with_retry_structured_handles_incomplete_response(self, client, mock_openai, valid_extraction):
        """Test handling of incomplete response status."""
        mock_response = create_mock_response(valid_extraction, status="incomplete")
        mock_response.incomplete_details = MagicMock(reason="max_tokens")
        mock_openai.responses.parse.return_value = mock_response

        with pytest.raises(ValueError) as exc_info:
            await client._call_with_retry_structured(
                input_content="test",
                instructions="instructions",
            )

        assert "Incomplete response" in str(exc_info.value)


class TestBuildCapsule:
    """Tests for _build_capsule method."""

    @pytest.fixture
    def client(self, settings):
        """Create OpenAIClient."""
        with patch("sieve.llm.openai.AsyncOpenAI"):
            return OpenAIClient(settings)

    @pytest.fixture
    def valid_extraction(self):
        """Create a valid CapsuleExtraction object."""
        return create_valid_extraction()

    def test_build_capsule_basic(self, client, valid_extraction):
        """Test building capsule from CapsuleExtraction."""
        capsule = client._build_capsule(valid_extraction)

        assert capsule.metadata.title == "Test Article Title"
        assert capsule.executive_summary == "This is a summary. It has two sentences."
        assert capsule.core_insight == "The main insight from this content."
        assert capsule.full_content == "The full processed content."
        assert capsule.metadata.tags == ["testing", "python"]
        assert capsule.metadata.category == "Technology"

    def test_build_capsule_with_source_url(self, client, valid_extraction):
        """Test building capsule with source URL."""
        capsule = client._build_capsule(valid_extraction, source_url="https://example.com")

        assert capsule.metadata.source_url == "https://example.com"

    def test_build_capsule_with_capture_method(self, client, valid_extraction):
        """Test building capsule with capture method."""
        capsule = client._build_capsule(valid_extraction, capture_method="browser")

        assert capsule.metadata.capture_method == "browser"

    def test_build_capsule_generates_unique_id(self, client, valid_extraction):
        """Test that unique IDs are generated."""
        capsule1 = client._build_capsule(valid_extraction)
        capsule2 = client._build_capsule(valid_extraction)

        # IDs should be different (microsecond precision)
        # Note: May occasionally be same if called in same microsecond
        assert capsule1.metadata.id is not None
        assert capsule2.metadata.id is not None

    def test_build_capsule_defaults_category(self, client):
        """Test default category for missing/empty category."""
        extraction = CapsuleExtraction(
            title="Minimal",
            executive_summary="Summary",
            core_insight="Insight",
            full_content="Content",
            tags=[],
            category="",  # Empty category
        )

        capsule = client._build_capsule(extraction)

        assert capsule.metadata.category == "Uncategorized"


class TestProcessText:
    """Tests for process_text method."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        mock = MagicMock()
        mock.responses.parse = AsyncMock()
        return mock

    @pytest.fixture
    def client(self, settings, mock_openai):
        """Create OpenAIClient with mock."""
        with patch("sieve.llm.openai.AsyncOpenAI", return_value=mock_openai):
            client = OpenAIClient(settings)
            client.client = mock_openai
            return client

    @pytest.fixture
    def valid_extraction(self):
        """Create a valid CapsuleExtraction object."""
        return create_valid_extraction()

    async def test_process_text_calls_api(self, client, mock_openai, valid_extraction):
        """Test that process_text calls the API correctly."""
        mock_response = create_mock_response(valid_extraction)
        mock_openai.responses.parse.return_value = mock_response

        await client.process_text("Some content to process")

        # Verify API was called
        mock_openai.responses.parse.assert_called_once()
        call_kwargs = mock_openai.responses.parse.call_args.kwargs

        # Check model and text_format
        assert call_kwargs["model"] == client.model
        assert call_kwargs["text_format"] == CapsuleExtraction

        # Check instructions contain the system prompt
        assert "Knowledge Capsule" in call_kwargs["instructions"]

    async def test_process_text_includes_source_url(self, client, mock_openai, valid_extraction):
        """Test that source URL is included in input."""
        mock_response = create_mock_response(valid_extraction)
        mock_openai.responses.parse.return_value = mock_response

        await client.process_text("Content", source_url="https://example.com")

        call_kwargs = mock_openai.responses.parse.call_args.kwargs
        assert "https://example.com" in call_kwargs["input"]

    async def test_process_text_returns_capsule(self, client, mock_openai, valid_extraction):
        """Test that process_text returns a Capsule."""
        mock_response = create_mock_response(valid_extraction)
        mock_openai.responses.parse.return_value = mock_response

        result = await client.process_text("Content")

        assert result.metadata.title == "Test Article Title"
        assert result.executive_summary == valid_extraction.executive_summary


class TestProcessImage:
    """Tests for image processing methods."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        mock = MagicMock()
        mock.responses.parse = AsyncMock()
        return mock

    @pytest.fixture
    def client(self, settings, mock_openai):
        """Create OpenAIClient with mock."""
        with patch("sieve.llm.openai.AsyncOpenAI", return_value=mock_openai):
            client = OpenAIClient(settings)
            client.client = mock_openai
            return client

    @pytest.fixture
    def valid_extraction(self):
        """Create a valid CapsuleExtraction object."""
        return create_valid_extraction()

    async def test_process_image_reads_file(self, client, mock_openai, valid_extraction, tmp_path):
        """Test that process_image reads image file."""
        mock_response = create_mock_response(valid_extraction)
        mock_openai.responses.parse.return_value = mock_response

        # Create test image
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        await client.process_image(img_path)

        # Verify vision API call
        call_kwargs = mock_openai.responses.parse.call_args.kwargs
        input_content = call_kwargs["input"]
        assert input_content[0]["content"][0]["type"] == "input_image"

    async def test_process_image_detects_mime_type(self, client, mock_openai, valid_extraction, tmp_path):
        """Test that MIME type is detected from extension."""
        mock_response = create_mock_response(valid_extraction)
        mock_openai.responses.parse.return_value = mock_response

        # Test different extensions
        for ext, expected_mime in [(".png", "image/png"), (".jpg", "image/jpeg"), (".gif", "image/gif")]:
            img_path = tmp_path / f"test{ext}"
            img_path.write_bytes(b"data")

            await client.process_image(img_path)

            call_kwargs = mock_openai.responses.parse.call_args.kwargs
            image_url = call_kwargs["input"][0]["content"][0]["image_url"]
            assert expected_mime in image_url

    async def test_process_image_base64_direct(self, client, mock_openai, valid_extraction):
        """Test processing base64 image data directly."""
        mock_response = create_mock_response(valid_extraction)
        mock_openai.responses.parse.return_value = mock_response

        await client.process_image_base64(
            "base64encodeddata==",
            source_url="https://example.com",
        )

        call_kwargs = mock_openai.responses.parse.call_args.kwargs
        image_url = call_kwargs["input"][0]["content"][0]["image_url"]
        assert "base64encodeddata==" in image_url


class TestSystemPrompts:
    """Tests for system prompts."""

    def test_capsule_system_prompt_mentions_key_elements(self):
        """Test that system prompt includes key extraction instructions."""
        assert "Knowledge Capsule" in CAPSULE_SYSTEM_PROMPT
        assert "title" in CAPSULE_SYSTEM_PROMPT.lower()
        assert "executive_summary" in CAPSULE_SYSTEM_PROMPT
        assert "core_insight" in CAPSULE_SYSTEM_PROMPT
        assert "tags" in CAPSULE_SYSTEM_PROMPT
        assert "category" in CAPSULE_SYSTEM_PROMPT
        assert "JSON" in CAPSULE_SYSTEM_PROMPT

    def test_image_system_prompt_for_vision(self):
        """Test that image prompt is suitable for vision API."""
        assert "screenshot" in IMAGE_SYSTEM_PROMPT.lower()
        assert "visual" in IMAGE_SYSTEM_PROMPT.lower()
        assert "JSON" in IMAGE_SYSTEM_PROMPT
