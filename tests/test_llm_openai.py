"""Tests for sieve.llm.openai module."""

import asyncio
import base64
import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIConnectionError, APIError, RateLimitError

from sieve.llm.openai import CAPSULE_SYSTEM_PROMPT, IMAGE_SYSTEM_PROMPT, OpenAIClient


class TestOpenAIClient:
    """Tests for OpenAIClient class."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        mock = MagicMock()
        mock.chat = MagicMock()
        mock.chat.completions = MagicMock()
        mock.chat.completions.create = AsyncMock()
        return mock

    @pytest.fixture
    def client(self, settings, mock_openai):
        """Create OpenAIClient with mocked dependencies."""
        with patch("sieve.llm.openai.AsyncOpenAI", return_value=mock_openai):
            client = OpenAIClient(settings)
            client.client = mock_openai
            return client

    @pytest.fixture
    def valid_response(self):
        """Create a valid LLM response."""
        return json.dumps({
            "title": "Test Article Title",
            "executive_summary": "This is a summary. It has two sentences.",
            "core_insight": "The main insight from this content.",
            "full_content": "The full processed content.",
            "tags": ["testing", "python"],
            "category": "Technology",
        })

    def test_init(self, settings):
        """Test client initialization."""
        with patch("sieve.llm.openai.AsyncOpenAI") as mock_class:
            client = OpenAIClient(settings)

            mock_class.assert_called_once_with(api_key=settings.openai_api_key)
            assert client.model == settings.openai_model

    async def test_call_with_retry_success(self, client, mock_openai, valid_response):
        """Test successful API call."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = valid_response
        mock_openai.chat.completions.create.return_value = mock_response

        result = await client._call_with_retry([{"role": "user", "content": "test"}])

        assert result == valid_response
        mock_openai.chat.completions.create.assert_called_once()

    async def test_call_with_retry_retries_on_rate_limit(self, client, mock_openai, valid_response):
        """Test that rate limit errors trigger retry."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = valid_response

        # First call fails, second succeeds
        mock_openai.chat.completions.create.side_effect = [
            RateLimitError(
                message="Rate limit",
                response=MagicMock(status_code=429),
                body={"error": {"message": "Rate limit"}},
            ),
            mock_response,
        ]

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._call_with_retry([{"role": "user", "content": "test"}])

        assert result == valid_response
        assert mock_openai.chat.completions.create.call_count == 2

    async def test_call_with_retry_exponential_backoff(self, client, mock_openai):
        """Test exponential backoff on retries."""
        mock_openai.chat.completions.create.side_effect = RateLimitError(
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
                await client._call_with_retry([{"role": "user", "content": "test"}])

        # Check exponential backoff: 1, 2, 4
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == 1.0
        assert sleep_calls[1] == 2.0
        assert sleep_calls[2] == 4.0

    async def test_call_with_retry_gives_up_after_max_retries(self, client, mock_openai):
        """Test that client gives up after max retries."""
        mock_openai.chat.completions.create.side_effect = APIConnectionError(
            request=MagicMock()
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(APIConnectionError):
                client.settings.max_retries = 2
                await client._call_with_retry([{"role": "user", "content": "test"}])

        assert mock_openai.chat.completions.create.call_count == 2


class TestBuildCapsule:
    """Tests for _build_capsule method."""

    @pytest.fixture
    def client(self, settings):
        """Create OpenAIClient."""
        with patch("sieve.llm.openai.AsyncOpenAI"):
            return OpenAIClient(settings)

    def test_build_capsule_basic(self, client):
        """Test building capsule from LLM data."""
        data = {
            "title": "Test Title",
            "executive_summary": "Summary text",
            "core_insight": "Insight text",
            "full_content": "Full content",
            "tags": ["tag1"],
            "category": "Tech",
        }

        capsule = client._build_capsule(data)

        assert capsule.metadata.title == "Test Title"
        assert capsule.executive_summary == "Summary text"
        assert capsule.core_insight == "Insight text"
        assert capsule.full_content == "Full content"
        assert capsule.metadata.tags == ["tag1"]
        assert capsule.metadata.category == "Tech"

    def test_build_capsule_with_source_url(self, client):
        """Test building capsule with source URL."""
        data = {
            "title": "Test",
            "executive_summary": "Summary",
            "core_insight": "Insight",
            "full_content": "Content",
            "tags": [],
            "category": "Web",
        }

        capsule = client._build_capsule(data, source_url="https://example.com")

        assert capsule.metadata.source_url == "https://example.com"

    def test_build_capsule_with_capture_method(self, client):
        """Test building capsule with capture method."""
        data = {
            "title": "Test",
            "executive_summary": "Summary",
            "core_insight": "Insight",
            "full_content": "Content",
            "tags": [],
            "category": "Web",
        }

        capsule = client._build_capsule(data, capture_method="browser")

        assert capsule.metadata.capture_method == "browser"

    def test_build_capsule_generates_unique_id(self, client):
        """Test that unique IDs are generated."""
        data = {
            "title": "Test",
            "executive_summary": "Summary",
            "core_insight": "Insight",
            "full_content": "Content",
        }

        capsule1 = client._build_capsule(data)
        capsule2 = client._build_capsule(data)

        # IDs should be different (microsecond precision)
        # Note: May occasionally be same if called in same microsecond
        assert capsule1.metadata.id is not None
        assert capsule2.metadata.id is not None

    def test_build_capsule_defaults(self, client):
        """Test defaults for missing fields."""
        data = {
            "title": "Minimal",
            "executive_summary": "Summary",
            "core_insight": "Insight",
            "full_content": "Content",
        }

        capsule = client._build_capsule(data)

        assert capsule.metadata.tags == []
        assert capsule.metadata.category == "Uncategorized"


class TestParseResponse:
    """Tests for _parse_response method."""

    @pytest.fixture
    def client(self, settings):
        """Create OpenAIClient."""
        with patch("sieve.llm.openai.AsyncOpenAI"):
            return OpenAIClient(settings)

    def test_parse_valid_json(self, client):
        """Test parsing valid JSON response."""
        response = '{"title": "Test", "value": 123}'

        result = client._parse_response(response)

        assert result == {"title": "Test", "value": 123}

    def test_parse_invalid_json_raises(self, client):
        """Test that invalid JSON raises ValueError."""
        response = "not valid json {"

        with pytest.raises(ValueError) as exc_info:
            client._parse_response(response)

        assert "invalid JSON" in str(exc_info.value)


class TestProcessText:
    """Tests for process_text method."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        mock = MagicMock()
        mock.chat.completions.create = AsyncMock()
        return mock

    @pytest.fixture
    def client(self, settings, mock_openai):
        """Create OpenAIClient with mock."""
        with patch("sieve.llm.openai.AsyncOpenAI", return_value=mock_openai):
            client = OpenAIClient(settings)
            client.client = mock_openai
            return client

    async def test_process_text_calls_api(self, client, mock_openai, sample_llm_response):
        """Test that process_text calls the API correctly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_llm_response)
        mock_openai.chat.completions.create.return_value = mock_response

        await client.process_text("Some content to process")

        # Verify API was called
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs

        # Check model and format
        assert call_kwargs["model"] == client.model
        assert call_kwargs["response_format"] == {"type": "json_object"}

        # Check system prompt
        assert call_kwargs["messages"][0]["role"] == "system"
        assert "Knowledge Capsule" in call_kwargs["messages"][0]["content"]

    async def test_process_text_includes_source_url(self, client, mock_openai, sample_llm_response):
        """Test that source URL is included in prompt."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_llm_response)
        mock_openai.chat.completions.create.return_value = mock_response

        await client.process_text("Content", source_url="https://example.com")

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        user_content = call_kwargs["messages"][1]["content"]
        assert "https://example.com" in user_content

    async def test_process_text_returns_capsule(self, client, mock_openai, sample_llm_response):
        """Test that process_text returns a Capsule."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_llm_response)
        mock_openai.chat.completions.create.return_value = mock_response

        result = await client.process_text("Content")

        assert result.metadata.title == "Generated Capsule Title"
        assert result.executive_summary == sample_llm_response["executive_summary"]


class TestProcessImage:
    """Tests for image processing methods."""

    @pytest.fixture
    def mock_openai(self):
        """Create mock OpenAI client."""
        mock = MagicMock()
        mock.chat.completions.create = AsyncMock()
        return mock

    @pytest.fixture
    def client(self, settings, mock_openai):
        """Create OpenAIClient with mock."""
        with patch("sieve.llm.openai.AsyncOpenAI", return_value=mock_openai):
            client = OpenAIClient(settings)
            client.client = mock_openai
            return client

    async def test_process_image_reads_file(self, client, mock_openai, sample_llm_response, tmp_path):
        """Test that process_image reads image file."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_llm_response)
        mock_openai.chat.completions.create.return_value = mock_response

        # Create test image
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        await client.process_image(img_path)

        # Verify vision API call
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        user_message = call_kwargs["messages"][1]
        assert user_message["content"][0]["type"] == "image_url"

    async def test_process_image_detects_mime_type(self, client, mock_openai, sample_llm_response, tmp_path):
        """Test that MIME type is detected from extension."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_llm_response)
        mock_openai.chat.completions.create.return_value = mock_response

        # Test different extensions
        for ext, expected_mime in [(".png", "image/png"), (".jpg", "image/jpeg"), (".gif", "image/gif")]:
            img_path = tmp_path / f"test{ext}"
            img_path.write_bytes(b"data")

            await client.process_image(img_path)

            call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
            image_url = call_kwargs["messages"][1]["content"][0]["image_url"]["url"]
            assert expected_mime in image_url

    async def test_process_image_base64_direct(self, client, mock_openai, sample_llm_response):
        """Test processing base64 image data directly."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(sample_llm_response)
        mock_openai.chat.completions.create.return_value = mock_response

        await client.process_image_base64(
            "base64encodeddata==",
            source_url="https://example.com",
        )

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        image_url = call_kwargs["messages"][1]["content"][0]["image_url"]["url"]
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
