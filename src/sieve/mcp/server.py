"""MCP server for Neural Sieve - AI integration via Model Context Protocol."""

import asyncio
from collections import defaultdict

from collections.abc import Iterable

from mcp.server import Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool
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
    settings = get_settings()
    server = Server("neural-sieve")

    def get_capsules() -> list[dict]:
        """Load all active capsules with content."""
        return load_capsules(settings, include_content=True)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="search_capsules",
                description="Search knowledge capsules by keyword. Returns matching capsules with their content.",
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
        """Search capsules by keyword."""
        capsules = get_capsules()
        query_lower = query.lower()

        matches = []
        for c in capsules:
            score = 0
            title = c.get("title", "").lower()
            tags = [t.lower() for t in c.get("tags", [])]
            content = c.get("_content", "").lower()

            if query_lower in title:
                score += 10
            if any(query_lower in t for t in tags):
                score += 5
            if query_lower in content:
                score += 1

            if score > 0:
                matches.append((score, c))

        matches.sort(key=lambda x: x[0], reverse=True)
        results = [c for _, c in matches[:limit]]

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

        if not pinned:
            return [TextContent(type="text", text="No pinned capsules (Eternal Truths) found.")]

        text = f"# Eternal Truths ({len(pinned)} pinned capsules)\n\n"
        for c in pinned:
            text += format_capsule(c)
            text += "\n---\n\n"

        return [TextContent(type="text", text=text)]

    async def get_capsule_by_id(capsule_id: str) -> list[TextContent]:
        """Get a specific capsule by ID."""
        capsules = get_capsules()

        for c in capsules:
            if c.get("id") == capsule_id:
                return [TextContent(type="text", text=format_capsule(c))]

        return [TextContent(type="text", text=f"Capsule with ID '{capsule_id}' not found.")]

    async def get_index() -> list[TextContent]:
        """Get the knowledge index content."""
        index_path = settings.index_path

        if not index_path.exists():
            return [TextContent(type="text", text="INDEX.md not found. Run 'sieve index' to generate it.")]

        content = index_path.read_text()
        return [TextContent(type="text", text=content)]

    async def get_categories() -> list[TextContent]:
        """Get all categories with counts."""
        capsules = get_capsules()
        by_category = defaultdict(int)

        for c in capsules:
            by_category[c.get("category", "Uncategorized")] += 1

        text = "# Knowledge Categories\n\n"
        for category in sorted(by_category.keys()):
            text += f"- **{category}**: {by_category[category]} capsules\n"

        text += f"\n**Total: {len(capsules)} capsules across {len(by_category)} categories**"

        return [TextContent(type="text", text=text)]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls using dictionary dispatch."""
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
            return await handler()

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(main())
