"""OpenAI client with retry logic using the Responses API."""

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
from .prompts import CAPSULE_SYSTEM_PROMPT, IMAGE_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class OpenAIClient:
    """OpenAI API client using the Responses API with exponential backoff retry."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    async def _call_with_retry(
        self,
        input_content: str | list[dict],
        instructions: str,
        max_tokens: int = 4096,
    ) -> str:
        """Make API call with exponential backoff retry."""
        last_error: Exception = RuntimeError("No API call attempted")
        delay = self.settings.retry_base_delay

        # Log input info
        if isinstance(input_content, str):
            input_preview = input_content[:100].replace("\n", " ")
            logger.debug(f"[LLM] Input text ({len(input_content)} chars): {input_preview}...")
        else:
            logger.debug(f"[LLM] Input: {len(input_content)} message(s) with image")

        logger.debug(f"[LLM] Model: {self.model}, max_tokens: {max_tokens}")

        for attempt in range(self.settings.max_retries):
            try:
                logger.debug(f"[LLM] API call attempt {attempt + 1}/{self.settings.max_retries}")
                response = await self.client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=input_content,
                    max_output_tokens=max_tokens,
                    text={"format": {"type": "json_object"}},
                )
                response_preview = (response.output_text or "")[:100].replace("\n", " ")
                logger.debug(f"[LLM] Response ({len(response.output_text or '')} chars): {response_preview}...")
                logger.info(f"[LLM] API call successful on attempt {attempt + 1}")
                return response.output_text
            except (RateLimitError, APIError, APIConnectionError) as e:
                last_error = e
                logger.warning(f"[LLM] API error: {e}, retrying in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
                delay *= 2
            except Exception as e:
                # Don't retry on auth errors or unexpected exceptions
                logger.error(f"[LLM] Unrecoverable error: {type(e).__name__}: {e}")
                raise

        logger.error(f"[LLM] All {self.settings.max_retries} attempts failed")
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
        logger.info(f"[LLM] Processing text ({len(content)} chars), source: {source_url or 'none'}")
        user_content = f"Source URL: {source_url}\n\n{content}" if source_url else content
        # Responses API requires 'json' in input when using json_object format
        user_content = f"{user_content}\n\nRespond in JSON format."

        response = await self._call_with_retry(
            input_content=user_content,
            instructions=CAPSULE_SYSTEM_PROMPT,
        )
        data = self._parse_response(response)

        capsule = self._build_capsule(data, source_url, capture_method)
        logger.info(f"[LLM] Created capsule: '{capsule.metadata.title}' [{capsule.metadata.category}]")
        return capsule

    async def _process_image_data(
        self,
        image_data: str,
        mime_type: str = "image/jpeg",
        source_url: Optional[str] = None,
        capture_method: str = "screenshot",
    ) -> Capsule:
        """Process base64 image data into a capsule using vision."""
        logger.info(f"[LLM] Processing image ({len(image_data)} base64 chars), mime: {mime_type}")
        # Responses API requires 'json' in input when using json_object format
        input_content = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_data}",
                    },
                    {
                        "type": "input_text",
                        "text": "Extract content from this image. Respond in JSON format.",
                    },
                ],
            },
        ]

        response = await self._call_with_retry(
            input_content=input_content,
            instructions=IMAGE_SYSTEM_PROMPT,
            max_tokens=4096,
        )
        data = self._parse_response(response)

        capsule = self._build_capsule(data, source_url, capture_method)
        logger.info(f"[LLM] Created capsule from image: '{capsule.metadata.title}' [{capsule.metadata.category}]")
        return capsule

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
