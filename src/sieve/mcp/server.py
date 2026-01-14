"""MCP server for Neural Sieve - AI integration via Model Context Protocol."""

from collections import defaultdict
from pathlib import Path
from typing import Optional

import frontmatter
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..config import get_settings


def run_server():
    """Run the MCP server."""
    settings = get_settings()
    server = Server("neural-sieve")

    def load_capsules() -> list[dict]:
        """Load all active capsules."""
        capsules = []
        capsules_dir = settings.capsules_path

        if not capsules_dir.exists():
            return capsules

        for md_file in capsules_dir.rglob("*.md"):
            try:
                post = frontmatter.load(md_file)
                capsule = dict(post.metadata)
                capsule["_path"] = str(md_file.relative_to(settings.vault_root))
                capsule["_content"] = post.content

                if capsule.get("status") != "legacy":
                    capsules.append(capsule)
            except Exception:
                pass

        return capsules

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
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
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
                name="get_readme",
                description="Get the full README.md index showing all capsules organized by category.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_categories",
                description="Get list of all knowledge categories with capsule counts.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls."""
        if name == "search_capsules":
            return await search_capsules(
                arguments.get("query", ""),
                arguments.get("limit", 10),
            )
        elif name == "get_pinned":
            return await get_pinned()
        elif name == "get_capsule":
            return await get_capsule(arguments.get("id", ""))
        elif name == "get_readme":
            return await get_readme()
        elif name == "get_categories":
            return await get_categories()
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def search_capsules(query: str, limit: int = 10) -> list[TextContent]:
        """Search capsules by keyword."""
        capsules = load_capsules()
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
        capsules = load_capsules()
        pinned = [c for c in capsules if c.get("pinned")]

        if not pinned:
            return [TextContent(type="text", text="No pinned capsules (Eternal Truths) found.")]

        text = f"# Eternal Truths ({len(pinned)} pinned capsules)\n\n"
        for c in pinned:
            text += format_capsule(c)
            text += "\n---\n\n"

        return [TextContent(type="text", text=text)]

    async def get_capsule(capsule_id: str) -> list[TextContent]:
        """Get a specific capsule by ID."""
        capsules = load_capsules()

        for c in capsules:
            if c.get("id") == capsule_id:
                return [TextContent(type="text", text=format_capsule(c))]

        return [TextContent(type="text", text=f"Capsule with ID '{capsule_id}' not found.")]

    async def get_readme() -> list[TextContent]:
        """Get the README.md content."""
        readme_path = settings.readme_path

        if not readme_path.exists():
            return [TextContent(type="text", text="README.md not found. Run 'sieve index' to generate it.")]

        content = readme_path.read_text()
        return [TextContent(type="text", text=content)]

    async def get_categories() -> list[TextContent]:
        """Get all categories with counts."""
        capsules = load_capsules()
        by_category = defaultdict(int)

        for c in capsules:
            by_category[c.get("category", "Uncategorized")] += 1

        text = "# Knowledge Categories\n\n"
        for category in sorted(by_category.keys()):
            text += f"- **{category}**: {by_category[category]} capsules\n"

        text += f"\n**Total: {len(capsules)} capsules across {len(by_category)} categories**"

        return [TextContent(type="text", text=text)]

    def format_capsule(c: dict) -> str:
        """Format a capsule for display."""
        lines = [
            f"## {c.get('title', 'Untitled')}",
            f"**ID:** {c.get('id', 'N/A')}",
            f"**Category:** {c.get('category', 'Uncategorized')}",
            f"**Tags:** {', '.join(c.get('tags', []))}",
            f"**Captured:** {c.get('captured_at', 'Unknown')}",
            f"**Pinned:** {'Yes' if c.get('pinned') else 'No'}",
        ]

        if c.get("source_url"):
            lines.append(f"**Source:** {c['source_url']}")

        lines.append("")
        lines.append(c.get("_content", ""))

        return "\n".join(lines)

    # Run the server
    import asyncio

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(main())
