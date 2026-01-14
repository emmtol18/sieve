"""OpenAI client with retry logic."""

import asyncio
import base64
import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError

from ..capsule.schema import Capsule, CapsuleMetadata
from ..config import Settings

logger = logging.getLogger(__name__)

CAPSULE_SYSTEM_PROMPT = """You are a knowledge extraction assistant for Neural Sieve, a personal knowledge management system.

Your job is to transform raw content into structured "Knowledge Capsules" - high-signal summaries that capture the most valuable insights.

For every piece of content, you must extract:
1. A compelling title (5-10 words)
2. An executive summary (2 sentences max) - the hook that explains why this matters
3. The core insight - the single most important "Aha!" moment
4. Cleaned full content - the complete text stripped of noise (ads, navigation, etc.)
5. Tags - 2-5 freeform topic tags
6. Category - a single broad category (e.g., Technology, Business, Philosophy, Science, Design, Psychology, Health, Creativity)

Respond with valid JSON matching this schema:
{
  "title": "string",
  "executive_summary": "string",
  "core_insight": "string",
  "full_content": "string",
  "tags": ["string"],
  "category": "string"
}"""

IMAGE_SYSTEM_PROMPT = """You are a visual content extraction assistant for Neural Sieve.

Analyze this screenshot and extract all meaningful text and information. Focus on:
1. Main content and key points
2. Any code, formulas, or structured data
3. Important visual elements (diagrams, charts) described in text

After extraction, structure the content as a Knowledge Capsule:
{
  "title": "string (5-10 words)",
  "executive_summary": "string (2 sentences)",
  "core_insight": "string (the key takeaway)",
  "full_content": "string (complete extracted text)",
  "tags": ["string"],
  "category": "string"
}

Respond with valid JSON only."""


class OpenAIClient:
    """OpenAI API client with exponential backoff retry."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def _call_with_retry(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
    ) -> str:
        """Make API call with exponential backoff retry."""
        last_error: Exception = RuntimeError("No API call attempted")
        delay = self.settings.retry_base_delay

        for attempt in range(self.settings.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content
            except (RateLimitError, APIError, APIConnectionError) as e:
                last_error = e
                logger.warning(f"API error: {e}, retrying in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                delay *= 2
            except Exception as e:
                # Don't retry on auth errors or unexpected exceptions
                raise

        raise last_error

    def _build_capsule(
        self,
        data: dict,
        source_url: Optional[str] = None,
        capture_method: str = "manual",
    ) -> Capsule:
        """Build a Capsule from LLM response data."""
        # Use microseconds for unique ID
        capsule_id = datetime.now().strftime("%Y-%m-%d-T%H%M%S-%f")[:23]

        metadata = CapsuleMetadata(
            id=capsule_id,
            title=data["title"],
            source_url=source_url,
            tags=data.get("tags", []),
            category=data.get("category", "Uncategorized"),
            captured_at=date.today(),
            capture_method=capture_method,
        )

        return Capsule(
            metadata=metadata,
            executive_summary=data["executive_summary"],
            core_insight=data["core_insight"],
            full_content=data["full_content"],
        )

    def _parse_response(self, response: str) -> dict:
        """Parse JSON response with error handling."""
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise ValueError(f"LLM returned invalid JSON: {response[:200]}...") from e

    async def process_text(
        self,
        content: str,
        source_url: Optional[str] = None,
        capture_method: str = "manual",
    ) -> Capsule:
        """Process text content into a capsule."""
        user_content = f"Source URL: {source_url}\n\n{content}" if source_url else content

        messages = [
            {"role": "system", "content": CAPSULE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        response = await self._call_with_retry(messages)
        data = self._parse_response(response)

        return self._build_capsule(data, source_url, capture_method)

    async def _process_image_data(
        self,
        image_data: str,
        mime_type: str = "image/jpeg",
        source_url: Optional[str] = None,
        capture_method: str = "screenshot",
    ) -> Capsule:
        """Process base64 image data into a capsule using vision."""
        messages = [
            {"role": "system", "content": IMAGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_data}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        response = await self._call_with_retry(messages, max_tokens=4096)
        data = self._parse_response(response)

        return self._build_capsule(data, source_url, capture_method)

    async def process_image(
        self,
        image_path: Path,
        capture_method: str = "screenshot",
    ) -> Capsule:
        """Process an image file into a capsule using vision."""
        image_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")

        # Detect mime type from file extension
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(image_path.suffix.lower(), "image/png")

        return await self._process_image_data(
            image_data,
            mime_type=mime_type,
            capture_method=capture_method,
        )

    async def process_image_base64(
        self,
        image_data: str,
        source_url: Optional[str] = None,
        capture_method: str = "browser",
    ) -> Capsule:
        """Process base64 image data into a capsule."""
        return await self._process_image_data(
            image_data,
            source_url=source_url,
            capture_method=capture_method,
        )
