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

    async def _expand_query(query: str) -> list[str]:
        """Expand search query with semantic variations using LLM.

        Returns list of search terms including original query.
        Falls back to [query] on any error.
        """
        try:
            response = await openai_client.chat.completions.create(
                model=settings.query_expansion_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Generate 3-5 semantic variations and related terms for a search query. "
                            "Include synonyms, related concepts, and common alternative phrasings. "
                            "Return only the terms, one per line, no explanations or numbering."
                        ),
                    },
                    {"role": "user", "content": f"Query: {query}"},
                ],
                max_tokens=100,
                temperature=0.3,
            )

            expanded = response.choices[0].message.content.strip().split("\n")
            terms = [query] + [t.strip() for t in expanded if t.strip()]
            logger.debug(f"[Search] Expanded '{query}' to: {terms[:6]}")
            return terms[:6]  # Cap at 6 total terms

        except Exception as e:
            logger.warning(f"[Search] Query expansion failed for '{query}': {e}, using keyword search")
            return [query]

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        logger.debug("[MCP] Client requested tool list")
        return [
            Tool(
                name="search_capsules",
                description="Search knowledge capsules with semantic expansion. Automatically expands queries with related terms (e.g., 'auth' finds 'authentication', 'login', etc.).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query (searches title, tags, and content)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 10)",
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
                description="Get the full knowledge index showing all capsules organized by category.",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="get_categories",
                description="Get list of all knowledge categories with capsule counts.",
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
        """Search capsules with semantic query expansion."""
        logger.debug(f"[MCP] Searching for: '{query}' (limit: {limit})")
        capsules = get_capsules()

        # Expand query semantically (falls back to keyword-only on error)
        search_terms = await _expand_query(query)
        logger.debug(f"[MCP] Search terms after expansion: {search_terms}")

        matches = []
        for c in capsules:
            score = 0
            title = c.get("title", "").lower()
            tags = [t.lower() for t in c.get("tags", [])]
            content = c.get("_content", "").lower()

            # Search with all expanded terms
            for term in search_terms:
                term_lower = term.lower()
                if term_lower in title:
                    score += 10
                if any(term_lower in t for t in tags):
                    score += 5
                if term_lower in content:
                    score += 1

            if score > 0:
                matches.append((score, c))

        matches.sort(key=lambda x: x[0], reverse=True)
        results = [c for _, c in matches[:limit]]

        logger.info(f"[MCP] Search '{query}': {len(results)} results from {len(capsules)} capsules")

        if not results:
            return [TextContent(type="text", text=f"No capsules found matching '{query}'")]

        text = f"Found {len(results)} capsules matching '{query}':\n\n"
        for c in results:
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
