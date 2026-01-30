"""Tests for MCP search functionality."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# The search functions are nested inside run_server(), so we test the logic
# by extracting and testing the key components directly.


class TestExtractKeywords:
    """Tests for keyword extraction."""

    def _extract_keywords(self, query: str) -> list[str]:
        """Reproduce the keyword extraction logic from server.py."""
        import re

        words = re.findall(r"\b\w{2,}\b", query.lower())
        return list(set([query.lower()] + words))

    def test_single_word(self):
        keywords = self._extract_keywords("banana")
        assert "banana" in keywords

    def test_multiple_words(self):
        keywords = self._extract_keywords("banana prompt image")
        assert "banana" in keywords
        assert "prompt" in keywords
        assert "image" in keywords

    def test_preserves_full_query(self):
        keywords = self._extract_keywords("banana prompt")
        assert "banana prompt" in keywords

    def test_filters_short_words(self):
        keywords = self._extract_keywords("a banana in the AI")
        assert "a" not in keywords
        assert "banana" in keywords
        assert "ai" in keywords


class TestKeywordMatchScore:
    """Tests for keyword matching and scoring."""

    def _keyword_match_score(self, capsule: dict, keywords: list[str]):
        """Reproduce the keyword matching logic from server.py."""
        title = capsule.get("title", "").lower()
        tags = " ".join(capsule.get("tags", [])).lower()
        content = capsule.get("_content", "").lower()

        score = 0
        matched_keywords = []

        for kw in keywords:
            if kw in title:
                score += 20
                matched_keywords.append(f"title:{kw}")
            if kw in tags:
                score += 15
                matched_keywords.append(f"tag:{kw}")
            if kw in content:
                score += 5
                matched_keywords.append(f"content:{kw}")

        return score, matched_keywords

    def test_title_match_highest_weight(self):
        capsule = {"title": "Banana Pro Prompts", "tags": [], "_content": ""}
        score, _ = self._keyword_match_score(capsule, ["banana"])
        assert score == 20

    def test_tag_match_medium_weight(self):
        capsule = {"title": "Unrelated", "tags": ["banana"], "_content": ""}
        score, _ = self._keyword_match_score(capsule, ["banana"])
        assert score == 15

    def test_content_match_low_weight(self):
        capsule = {"title": "Unrelated", "tags": [], "_content": "about banana"}
        score, _ = self._keyword_match_score(capsule, ["banana"])
        assert score == 5

    def test_multiple_matches_accumulate(self):
        capsule = {
            "title": "Banana Pro Prompts",
            "tags": ["banana", "image generation"],
            "_content": "banana prompt engineering for image generation",
        }
        score, matched = self._keyword_match_score(capsule, ["banana", "prompt", "image"])
        # banana: title(20) + tag(15) + content(5) = 40
        # prompt: title(20) + content(5) = 25
        # image: tag(15) + content(5) = 20
        assert score == 85
        assert len(matched) > 3

    def test_no_match_returns_zero(self):
        capsule = {"title": "React Performance", "tags": ["react"], "_content": "react hooks"}
        score, matched = self._keyword_match_score(capsule, ["banana"])
        assert score == 0
        assert matched == []


class TestLLMRankingResponseParsing:
    """Tests for parsing LLM ranking responses."""

    def _parse_scores(self, raw_content: str | None) -> list[int] | None:
        """Reproduce the score parsing logic from server.py."""
        if not raw_content:
            return None

        scores_text = raw_content.strip()
        if "```" in scores_text:
            scores_text = scores_text.split("```")[1].replace("json", "").strip()
        return json.loads(scores_text)

    def test_parse_simple_array(self):
        scores = self._parse_scores("[10, 8, 3, 0, 5]")
        assert scores == [10, 8, 3, 0, 5]

    def test_parse_markdown_code_block(self):
        scores = self._parse_scores("```json\n[10, 8, 3]\n```")
        assert scores == [10, 8, 3]

    def test_parse_none_returns_none(self):
        assert self._parse_scores(None) is None

    def test_parse_empty_string_returns_none(self):
        assert self._parse_scores("") is None

    def test_parse_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            self._parse_scores("not json")


class TestLLMRankingIntegration:
    """Integration tests that verify the OpenAI API call works.

    These tests call the real API and require OPENAI_API_KEY to be set.
    Skip with: pytest -m 'not integration'
    """

    @pytest.fixture
    def real_settings(self):
        """Load real settings (requires .env with valid API key)."""
        from sieve.config import get_settings

        try:
            settings = get_settings()
            if not settings.openai_api_key or settings.openai_api_key == "test-api-key":
                pytest.skip("No real API key configured")
            return settings
        except Exception:
            pytest.skip("Cannot load settings")

    @pytest.mark.integration
    async def test_llm_ranking_returns_valid_scores(self, real_settings):
        """Verify the API returns parseable scores with enough tokens."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=real_settings.openai_api_key)

        response = await client.chat.completions.create(
            model=real_settings.query_expansion_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a search relevance ranker. "
                        "Return ONLY a JSON array of scores 0-10. Example: [8, 2, 10]"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Rate relevance to 'banana image generation prompts':\n"
                        "1. Banana Pro Prompts (tags: image generation, prompts)\n"
                        "2. React Performance (tags: react, next.js)\n"
                        "3. Voice Cloning TTS (tags: tts, audio)"
                    ),
                },
            ],
            max_completion_tokens=2048,
        )

        content = response.choices[0].message.content
        assert content, f"Empty response (finish_reason={response.choices[0].finish_reason})"
        assert response.choices[0].finish_reason == "stop", (
            f"Response truncated: finish_reason={response.choices[0].finish_reason}, "
            f"reasoning_tokens={response.usage.completion_tokens_details.reasoning_tokens}"
        )

        scores = json.loads(content)
        assert isinstance(scores, list)
        assert len(scores) == 3
        assert scores[0] >= 7, f"Banana Pro should score high, got {scores[0]}"
        assert scores[1] <= 3, f"React should score low, got {scores[1]}"
        assert scores[2] <= 3, f"TTS should score low, got {scores[2]}"

    @pytest.mark.integration
    async def test_max_completion_tokens_sufficient(self, real_settings):
        """Verify 2048 tokens is enough for ranking 15 capsules."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=real_settings.openai_api_key)

        # Build 15 capsule summaries (matching real server behavior)
        capsules = "\n".join(
            f"{i+1}. **Capsule {i+1}** (tags: tag{i})\n   Preview: Some content..."
            for i in range(15)
        )

        response = await client.chat.completions.create(
            model=real_settings.query_expansion_model,
            messages=[
                {
                    "role": "system",
                    "content": "Return ONLY a JSON array of 15 scores 0-10.",
                },
                {
                    "role": "user",
                    "content": f"Rate relevance to 'test query':\n\n{capsules}",
                },
            ],
            max_completion_tokens=2048,
        )

        content = response.choices[0].message.content
        assert content, "Empty response - need more tokens"
        assert response.choices[0].finish_reason == "stop"

        scores = json.loads(content)
        assert len(scores) == 15
