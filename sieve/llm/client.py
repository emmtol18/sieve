import json
import logging

from openai import AsyncOpenAI

from sieve.config import settings
from sieve.llm.prompts import CAPSULE_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=settings.fuel_api_key, base_url=settings.fuel_api_base)
        self.model = settings.fuel_model

    async def extract_capsule(self, content: str) -> dict:
        """Extract structured capsule data from raw content using an LLM.

        Calls OpenAI with the CAPSULE_EXTRACTION_PROMPT and parses the JSON response.
        Sets full_content to the original content.

        Returns a dict matching CapsuleCreate fields.
        """
        prompt = CAPSULE_EXTRACTION_PROMPT.format(content=content[:8000])

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON: %s", raw[:200])
            result = {}

        # Ensure required fields have defaults
        result.setdefault("title", "Untitled Capsule")
        result.setdefault("executive_summary", "")
        result.setdefault("core_insight", "")
        result.setdefault("tags", [])
        result.setdefault("keywords", [])
        result.setdefault("topics", [])
        result.setdefault("category", "")
        result.setdefault("domain", "")
        result.setdefault("difficulty", "beginner")
        result.setdefault("content_type", "insight")
        result.setdefault("source_type", "other")

        # Always store the original content
        result["full_content"] = content

        return result

    async def rank_capsules(self, query: str, capsules: list[dict]) -> list[dict]:
        """Rank capsules by relevance to a query using an LLM.

        Builds summaries of each capsule, asks the LLM to rate relevance 0-10.
        Returns a list of {index, score} dicts sorted by score descending.
        """
        if not capsules:
            return []

        summaries = []
        for i, c in enumerate(capsules):
            title = c.get("title", "Untitled")
            summary = c.get("executive_summary", "")
            summaries.append(f"[{i}] {title}: {summary}")

        summaries_text = "\n".join(summaries)

        prompt = (
            f"Given the search query: \"{query}\"\n\n"
            f"Rate the relevance of each capsule on a scale of 0-10.\n\n"
            f"Capsules:\n{summaries_text}\n\n"
            f"Return ONLY a JSON array of objects with 'index' (int) and 'score' (float) fields, "
            f"sorted by score descending."
        )

        response = await self.client.chat.completions.create(
            model=settings.fuel_search_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
            # Handle both {"results": [...]} and direct array
            if isinstance(data, dict):
                rankings = data.get("results", data.get("rankings", []))
            else:
                rankings = data
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for ranking: %s", raw[:200])
            rankings = []

        return sorted(rankings, key=lambda x: x.get("score", 0), reverse=True)
