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
        """Verify 4096 tokens is enough for ranking 50 capsules with compact format."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=real_settings.openai_api_key)

        # Build 50 capsule summaries using compact format (matching real server behavior)
        capsules = "\n".join(
            f"{i+1}. Capsule {i+1} [Category{i % 5}] (tags: tag{i})"
            for i in range(50)
        )

        response = await client.chat.completions.create(
            model=real_settings.query_expansion_model,
            messages=[
                {
                    "role": "system",
                    "content": "Return ONLY a JSON array of 50 scores 0-10.",
                },
                {
                    "role": "user",
                    "content": f"Rate relevance to 'test query':\n\n{capsules}",
                },
            ],
            max_completion_tokens=4096,
        )

        content = response.choices[0].message.content
        assert content, "Empty response - need more tokens"
        assert response.choices[0].finish_reason == "stop"

        scores = json.loads(content)
        assert len(scores) == 50


class TestBuildCapsuleSummaries:
    """Tests for compact capsule summary format."""

    def _build_capsule_summaries(self, capsules: list[dict]) -> str:
        """Reproduce the summary building logic from server.py."""
        lines = []
        for i, c in enumerate(capsules):
            title = c.get("title", "Untitled")
            category = c.get("category", "Uncategorized")
            tags = ", ".join(c.get("tags", []))
            lines.append(f"{i+1}. {title} [{category}] (tags: {tags})")
        return "\n".join(lines)

    def test_format_single_capsule(self):
        capsules = [{"title": "Test Capsule", "category": "Tech", "tags": ["ai", "ml"]}]
        result = self._build_capsule_summaries(capsules)
        assert result == "1. Test Capsule [Tech] (tags: ai, ml)"

    def test_numbering_starts_at_one(self):
        capsules = [
            {"title": "First", "category": "A", "tags": []},
            {"title": "Second", "category": "B", "tags": ["x"]},
        ]
        result = self._build_capsule_summaries(capsules)
        lines = result.split("\n")
        assert lines[0].startswith("1. ")
        assert lines[1].startswith("2. ")

    def test_missing_fields_use_defaults(self):
        capsules = [{}]
        result = self._build_capsule_summaries(capsules)
        assert result == "1. Untitled [Uncategorized] (tags: )"

    def test_multiple_tags_comma_separated(self):
        capsules = [{"title": "T", "category": "C", "tags": ["a", "b", "c"]}]
        result = self._build_capsule_summaries(capsules)
        assert "(tags: a, b, c)" in result


class TestCategoryPreFilter:
    """Tests for category pre-filtering logic."""

    CAPSULES = [
        {"title": "A", "category": "Technology", "tags": []},
        {"title": "B", "category": "Productivity", "tags": []},
        {"title": "C", "category": "Technology", "tags": []},
        {"title": "D", "category": "Learning", "tags": []},
    ]

    def _filter_by_category(self, capsules: list[dict], category: str | None) -> list[dict]:
        """Reproduce the category filter logic from server.py."""
        if not category:
            return capsules
        filtered = [c for c in capsules if category.lower() in c.get("category", "").lower()]
        return filtered if filtered else capsules

    def test_exact_match(self):
        result = self._filter_by_category(self.CAPSULES, "Technology")
        assert len(result) == 2
        assert all(c["category"] == "Technology" for c in result)

    def test_case_insensitive(self):
        result = self._filter_by_category(self.CAPSULES, "technology")
        assert len(result) == 2

    def test_substring_match(self):
        result = self._filter_by_category(self.CAPSULES, "tech")
        assert len(result) == 2

    def test_no_match_returns_all(self):
        result = self._filter_by_category(self.CAPSULES, "nonexistent")
        assert len(result) == 4

    def test_none_returns_all(self):
        result = self._filter_by_category(self.CAPSULES, None)
        assert len(result) == 4


class TestKeywordFallbackNormalization:
    """Tests for keyword fallback score normalization."""

    def _keyword_match_score(self, capsule: dict, keywords: list[str]):
        """Reproduce the keyword matching logic from server.py."""
        import re

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

    def _keyword_fallback(self, query: str, capsules: list[dict]) -> list[tuple[float, dict]]:
        """Reproduce the keyword fallback logic from server.py."""
        import re

        words = re.findall(r"\b\w{2,}\b", query.lower())
        keywords = list(set([query.lower()] + words))

        scored = []
        for c in capsules:
            raw_score, matched = self._keyword_match_score(c, keywords)
            normalized = min(raw_score / 4.0, 10.0)
            if normalized > 0:
                scored.append((normalized, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def test_title_match_normalizes_to_5(self):
        """Title-only match (raw 20) should normalize to 5.0."""
        capsules = [{"title": "Banana Guide", "tags": [], "_content": ""}]
        result = self._keyword_fallback("banana", capsules)
        assert len(result) == 1
        assert result[0][0] == 5.0

    def test_title_plus_tag_normalizes_to_8_75(self):
        """Title + tag match (raw 35) should normalize to 8.75."""
        capsules = [{"title": "Banana Guide", "tags": ["banana"], "_content": ""}]
        result = self._keyword_fallback("banana", capsules)
        assert len(result) == 1
        assert result[0][0] == 8.75

    def test_caps_at_10(self):
        """Very high raw scores should cap at 10.0."""
        capsules = [{"title": "Banana Guide", "tags": ["banana"], "_content": "banana banana"}]
        result = self._keyword_fallback("banana", capsules)
        assert len(result) == 1
        assert result[0][0] == 10.0

    def test_no_match_excluded(self):
        """Capsules with no keyword match should not appear in results."""
        capsules = [{"title": "React Guide", "tags": ["react"], "_content": "react hooks"}]
        result = self._keyword_fallback("banana", capsules)
        assert len(result) == 0

    def test_sorted_descending(self):
        """Results should be sorted by score descending."""
        capsules = [
            {"title": "Unrelated", "tags": [], "_content": "banana"},  # content only: raw 5 -> 1.25
            {"title": "Banana Guide", "tags": ["banana"], "_content": "banana"},  # raw 40 -> 10.0
        ]
        result = self._keyword_fallback("banana", capsules)
        assert len(result) == 2
        assert result[0][0] > result[1][0]
