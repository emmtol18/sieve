import logging

from sieve.api.capsules.schemas import CaptureRequest
from sieve.api.capture.scraper import extract_text_from_html, fetch_url
from sieve.llm.client import LLMClient

logger = logging.getLogger(__name__)


class CapturePipeline:
    """Pipeline for processing capture requests into capsule data.

    Handles both direct text content and URL-based capture:
    1. If a URL is provided, fetches and extracts text from the page
    2. Sends content to the LLM for structured extraction
    3. Returns a dict ready for capsule creation
    """

    def __init__(self) -> None:
        self.llm = LLMClient()

    async def process(self, req: CaptureRequest) -> dict:
        """Process a capture request into capsule data.

        Args:
            req: CaptureRequest with content and/or URL

        Returns:
            dict matching CapsuleCreate fields
        """
        content = req.content

        if req.url:
            html = await fetch_url(req.url)
            content = extract_text_from_html(html)

        if not content:
            raise ValueError("No content to process. Provide text content or a valid URL.")

        result = await self.llm.extract_capsule(content)

        # Set provenance metadata
        result["source_url"] = req.source_url or req.url
        result["capture_method"] = "url" if req.url else "manual"

        return result
