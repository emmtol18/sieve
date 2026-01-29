"""MCP server for Neural Sieve - AI integration via Model Context Protocol."""

import asyncio
import logging
import sys
from collections import defaultdict

from collections.abc import Iterable

# Configure logging to stderr (stdout is reserved for JSON-RPC)
# These logs appear in ~/Library/Logs/Claude/mcp-server-neural-sieve.log
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
from openai import AsyncOpenAI
from pydantic import AnyUrl

from ..capsule import load_capsules
from ..config import get_settings


def format_capsule(capsule: dict) -> str:
    """Format a capsule for display."""
    lines = [
        f"## {capsule.get('title', 'Untitled')}",
        f"**ID:** {capsule.get('id', 'N/A')}",
        f"**Category:** {capsule.get('category', 'Uncategorized')}",
        f"**Tags:** {', '.join(capsule.get('tags', []))}",
        f"**Captured:** {capsule.get('captured_at', 'Unknown')}",
        f"**Pinned:** {'Yes' if capsule.get('pinned') else 'No'}",
    ]

    if capsule.get("source_url"):
        lines.append(f"**Source:** {capsule['source_url']}")

    lines.append("")
    lines.append(capsule.get("_content", ""))

    return "\n".join(lines)


def run_server():
    """Run the MCP server."""
    logger.info("[MCP] Starting Neural Sieve MCP server...")

    settings = get_settings()
    logger.info(f"[MCP] Vault: {settings.vault_root}")

    server = Server("neural-sieve")

    # Create OpenAI client once for query expansion (reused across requests)
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    logger.debug(f"[MCP] OpenAI client initialized (model: {settings.query_expansion_model})")

    def get_capsules() -> list[dict]:
        """Load all active capsules with content."""
        capsules = load_capsules(settings, include_content=True)
        logger.debug(f"[MCP] Loaded {len(capsules)} capsules from vault")
        return capsules

    def _extract_keywords(query: str) -> list[str]:
        """Extract individual keywords from query for word-level matching."""
        import re
        # Split on whitespace and punctuation, keep words 2+ chars
        words = re.findall(r'\b\w{2,}\b', query.lower())
        # Also keep the original query for phrase matching
        return list(set([query.lower()] + words))

    def _keyword_match_score(capsule: dict, keywords: list[str]) -> int:
        """Score a capsule based on keyword matches (word-level).

        Returns a score where higher = more matches.
        """
        title = capsule.get("title", "").lower()
        tags = " ".join(capsule.get("tags", [])).lower()
        content = capsule.get("_content", "").lower()

        score = 0
        matched_keywords = []

        for kw in keywords:
            # Title matches (highest weight)
            if kw in title:
                score += 20
                matched_keywords.append(f"title:{kw}")
            # Tag matches (high weight)
            if kw in tags:
                score += 15
                matched_keywords.append(f"tag:{kw}")
            # Content matches (base weight)
            if kw in content:
                score += 5
                matched_keywords.append(f"content:{kw}")

        return score, matched_keywords

    async def _llm_rank_capsules(query: str, candidates: list[dict]) -> list[tuple[float, dict]]:
        """Use LLM to rank candidate capsules by relevance to user query.

        Returns list of (relevance_score, capsule) tuples sorted by relevance.
        """
        if not candidates:
            return []

        # Build a summary of each candidate for the LLM to evaluate
        summaries = []
        for i, c in enumerate(candidates):
            title = c.get("title", "Untitled")
            tags = ", ".join(c.get("tags", []))
            # Get first 200 chars of content as preview
            content_preview = c.get("_content", "")[:300].replace("\n", " ")
            summaries.append(f"{i+1}. **{title}** (tags: {tags})\n   Preview: {content_preview}...")

        capsule_list = "\n\n".join(summaries)

        try:
            response = await openai_client.chat.completions.create(
                model=settings.query_expansion_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a search relevance ranker. Given a user's search query and a list of knowledge capsules, "
                            "rate how relevant each capsule is to the query on a scale of 0-10.\n\n"
                            "Return ONLY a JSON array of scores in order, like: [8, 2, 10, 5]\n"
                            "Consider:\n"
                            "- Direct topic match (highest relevance)\n"
                            "- Related concepts or tools mentioned\n"
                            "- Partial matches or tangential relevance\n"
                            "Be generous - if there's any reasonable connection, score it above 0."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Query: {query}\n\nCapsules to rank:\n\n{capsule_list}"
                    },
                ],
                max_completion_tokens=100,
            )

            # Parse the JSON array of scores
            import json
            scores_text = response.choices[0].message.content.strip()
            # Handle potential markdown code blocks
            if "```" in scores_text:
                scores_text = scores_text.split("```")[1].replace("json", "").strip()
            scores = json.loads(scores_text)

            logger.debug(f"[Search] LLM relevance scores: {scores}")

            # Pair scores with capsules
            ranked = []
            for i, c in enumerate(candidates):
                score = scores[i] if i < len(scores) else 0
                ranked.append((score, c))

            # Sort by score descending
            ranked.sort(key=lambda x: x[0], reverse=True)
            return ranked

        except Exception as e:
            logger.warning(f"[Search] LLM ranking failed: {e}, using keyword scores")
            # Fall back to returning candidates as-is
            return [(5, c) for c in candidates]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        logger.debug("[MCP] Client requested tool list")
        return [
            Tool(
                name="search_capsules",
                description=(
                    "Search the user's personal knowledge base for relevant capsules. "
                    "Capsules contain curated insights, techniques, prompts, workflows, and learnings.\n\n"
                    "AUTOMATIC: At conversation start, search based on the user's first message. "
                    "Extract 2-4 key concepts and search. Only capsules scoring 6+/10 are returned.\n\n"
                    "If no relevant capsules are found, that's fine - continue without additional context.\n\n"
                    "Use individual keywords, not phrases. Search multiple times for thorough coverage."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Space-separated keywords (2-4 key concepts from user's message)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_pinned",
                description="Get all pinned capsules (Eternal Truths). These represent the highest-priority knowledge.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_capsule",
                description="Get a specific capsule by its ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "The capsule ID (e.g., 2026-01-14-T100000)",
                        },
                    },
                    "required": ["id"],
                },
            ),
            Tool(
                name="get_index",
                description=(
                    "Get the full knowledge index showing all capsules organized by category. "
                    "Use this FIRST when you need to understand what knowledge is available, "
                    "or when searches don't find what you're looking for. "
                    "The index shows capsule titles which can help you identify relevant topics to search for."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_categories",
                description=(
                    "Get list of all knowledge categories with capsule counts. "
                    "Use this to quickly see what domains of knowledge are available "
                    "(e.g., Technology, Productivity, Learning) before diving into searches."
                ),
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    # ==================== MCP Resources ====================
    # Resources provide passive context injection - knowledge available without tool calls

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available resources for context injection."""
        logger.debug("[MCP] Client requested resource list")
        resources = [
            Resource(
                uri=AnyUrl("capsules://pinned"),
                name="Pinned Knowledge (Eternal Truths)",
                description="High-priority knowledge capsules marked as 'Eternal Truths'. These represent your most important, verified insights and should be considered authoritative context.",
                mimeType="text/markdown",
            ),
            Resource(
                uri=AnyUrl("capsules://index"),
                name="Knowledge Index",
                description="Complete index of all available knowledge capsules organized by category. Use this to understand what knowledge is available and find relevant capsules to explore.",
                mimeType="text/markdown",
            ),
        ]
        return resources

    @server.read_resource()
    async def read_resource(uri: AnyUrl) -> Iterable[ReadResourceContents]:
        """Read a specific resource by URI."""
        uri_str = str(uri)
        logger.info(f"[MCP] Resource read: {uri_str}")

        if uri_str == "capsules://pinned":
            try:
                capsules = get_capsules()
                pinned = [c for c in capsules if c.get("pinned")]

                if not pinned:
                    text = "# Eternal Truths\n\nNo pinned capsules yet. Pin important insights to make them always available in context."
                else:
                    text = f"# Eternal Truths ({len(pinned)} pinned capsules)\n\n"
                    text += "These are your highest-priority knowledge capsules - insights you've marked as fundamental truths.\n\n"
                    for c in pinned:
                        text += format_capsule(c)
                        text += "\n---\n\n"

                return [ReadResourceContents(content=text, mime_type="text/markdown")]
            except Exception as e:
                return [ReadResourceContents(
                    content=f"# Eternal Truths\n\nError loading capsules: {e}",
                    mime_type="text/markdown",
                )]

        elif uri_str == "capsules://index":
            index_path = settings.index_path
            if not index_path.exists():
                return [ReadResourceContents(
                    content="# Knowledge Index\n\nNo index available. Run 'sieve index' to generate it.",
                    mime_type="text/markdown",
                )]

            try:
                content = index_path.read_text()
                return [ReadResourceContents(content=content, mime_type="text/markdown")]
            except Exception as e:
                return [ReadResourceContents(
                    content=f"# Knowledge Index\n\nError reading index: {e}",
                    mime_type="text/markdown",
                )]

        else:
            return [ReadResourceContents(
                content=f"Unknown resource: {uri_str}",
                mime_type="text/plain",
            )]

    async def search_capsules(query: str, limit: int = 10) -> list[TextContent]:
        """Search capsules using keyword matching + LLM relevance ranking.

        Two-phase search:
        1. Fast keyword filter to find candidates (word-level matching)
        2. LLM ranks candidates by semantic relevance to query

        Only returns capsules scoring >= relevance_threshold (default 6/10).
        """
        threshold = settings.relevance_threshold
        logger.info(f"[MCP] Searching for: '{query}' (limit: {limit}, threshold: {threshold})")
        capsules = get_capsules()

        # Phase 1: Extract keywords and find candidates with any match
        keywords = _extract_keywords(query)
        logger.debug(f"[MCP] Keywords extracted: {keywords}")

        candidates = []
        for c in capsules:
            score, matched = _keyword_match_score(c, keywords)
            if score > 0:
                candidates.append((score, matched, c))
                logger.debug(f"[MCP] Candidate: {c.get('title')} (score={score}, matched={matched})")

        logger.info(f"[MCP] Phase 1: {len(candidates)} keyword matches from {len(capsules)} capsules")

        if not candidates:
            return [TextContent(type="text", text=f"No capsules found matching '{query}'")]

        # Sort by keyword score first
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Phase 2: Use LLM to rank top candidates by semantic relevance
        # Only send top candidates to LLM to save tokens
        top_candidates = [c for _, _, c in candidates[:min(15, len(candidates))]]

        logger.info(f"[MCP] Phase 2: LLM ranking {len(top_candidates)} candidates...")
        ranked = await _llm_rank_capsules(query, top_candidates)

        # Filter by relevance threshold (default 6/10 for high signal)
        results = [(score, c) for score, c in ranked if score >= threshold][:limit]

        if not results:
            logger.info(f"[MCP] No capsules scored {threshold}+ for '{query}'")
            return [TextContent(type="text", text=f"No highly relevant capsules found for '{query}' (threshold: {threshold}/10)")]

        logger.info(f"[MCP] Search '{query}': returning {len(results)} results (scored {threshold}+)")

        text = f"Found {len(results)} relevant capsules:\n\n"
        for relevance, c in results:
            text += f"**Relevance: {relevance}/10**\n"
            text += format_capsule(c)
            text += "\n---\n\n"

        return [TextContent(type="text", text=text)]

    async def get_pinned() -> list[TextContent]:
        """Get all pinned capsules."""
        capsules = get_capsules()
        pinned = [c for c in capsules if c.get("pinned")]

        logger.info(f"[MCP] get_pinned: {len(pinned)} pinned capsules found")

        if not pinned:
            return [TextContent(type="text", text="No pinned capsules (Eternal Truths) found.")]

        text = f"# Eternal Truths ({len(pinned)} pinned capsules)\n\n"
        for c in pinned:
            text += format_capsule(c)
            text += "\n---\n\n"

        return [TextContent(type="text", text=text)]

    async def get_capsule_by_id(capsule_id: str) -> list[TextContent]:
        """Get a specific capsule by ID."""
        logger.debug(f"[MCP] Looking up capsule: {capsule_id}")
        capsules = get_capsules()

        for c in capsules:
            if c.get("id") == capsule_id:
                logger.info(f"[MCP] get_capsule: found '{c.get('title', 'Untitled')}'")
                return [TextContent(type="text", text=format_capsule(c))]

        logger.warning(f"[MCP] get_capsule: '{capsule_id}' not found")
        return [TextContent(type="text", text=f"Capsule with ID '{capsule_id}' not found.")]

    async def get_index() -> list[TextContent]:
        """Get the knowledge index content."""
        index_path = settings.index_path

        if not index_path.exists():
            logger.warning(f"[MCP] get_index: INDEX.md not found at {index_path}")
            return [TextContent(type="text", text="INDEX.md not found. Run 'sieve index' to generate it.")]

        content = index_path.read_text()
        logger.info(f"[MCP] get_index: returned {len(content)} chars")
        return [TextContent(type="text", text=content)]

    async def get_categories() -> list[TextContent]:
        """Get all categories with counts."""
        capsules = get_capsules()
        by_category = defaultdict(int)

        for c in capsules:
            by_category[c.get("category", "Uncategorized")] += 1

        logger.info(f"[MCP] get_categories: {len(capsules)} capsules in {len(by_category)} categories")

        text = "# Knowledge Categories\n\n"
        for category in sorted(by_category.keys()):
            text += f"- **{category}**: {by_category[category]} capsules\n"

        text += f"\n**Total: {len(capsules)} capsules across {len(by_category)} categories**"

        return [TextContent(type="text", text=text)]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls using dictionary dispatch."""
        logger.info(f"[MCP] Tool call: {name} with args: {arguments}")

        tool_handlers = {
            "search_capsules": lambda: search_capsules(
                arguments.get("query", ""),
                arguments.get("limit", 10),
            ),
            "get_pinned": get_pinned,
            "get_capsule": lambda: get_capsule_by_id(arguments.get("id", "")),
            "get_index": get_index,
            "get_categories": get_categories,
        }

        handler = tool_handlers.get(name)
        if handler:
            try:
                result = await handler()
                logger.info(f"[MCP] Tool {name} completed successfully")
                return result
            except Exception as e:
                logger.error(f"[MCP] Tool {name} failed: {e}")
                return [TextContent(type="text", text=f"Error in {name}: {e}")]

        logger.warning(f"[MCP] Unknown tool requested: {name}")
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def main():
        logger.info("[MCP] Server ready, waiting for connections...")
        async with stdio_server() as (read_stream, write_stream):
            logger.info("[MCP] Client connected via stdio")
            await server.run(read_stream, write_stream, server.create_initialization_options())
        logger.info("[MCP] Server shutting down")

    asyncio.run(main())
