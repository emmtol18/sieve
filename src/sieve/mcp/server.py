"""MCP server for Neural Sieve — exposes capsule tools for Claude Code."""

import json
import os
from collections import defaultdict

from mcp.server import Server
from mcp.types import TextContent, Tool

from sieve.mcp.api_client import SieveAPIClient

server = Server("neural-sieve")


def get_client() -> SieveAPIClient:
    """Create an API client from environment variables."""
    return SieveAPIClient(
        api_url=os.environ.get("SIEVE_API_URL", "http://localhost:8420"),
        api_key=os.environ.get("SIEVE_API_KEY", ""),
    )


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


def format_capsule(c: dict) -> str:
    """Format a single capsule as full markdown."""
    lines = [f"# {c.get('title', 'Untitled')}"]

    meta_parts = []
    if c.get("category"):
        meta_parts.append(f"**Category:** {c['category']}")
    if c.get("domain"):
        meta_parts.append(f"**Domain:** {c['domain']}")
    if c.get("tags"):
        meta_parts.append(f"**Tags:** {', '.join(c['tags'])}")
    if c.get("id"):
        meta_parts.append(f"**ID:** {c['id']}")
    if meta_parts:
        lines.append(" | ".join(meta_parts))

    if c.get("executive_summary"):
        lines.append(f"\n## Summary\n{c['executive_summary']}")
    if c.get("core_insight"):
        lines.append(f"\n## Core Insight\n{c['core_insight']}")
    if c.get("full_content"):
        lines.append(f"\n## Content\n{c['full_content']}")

    return "\n".join(lines)


def format_capsule_list(data: dict) -> str:
    """Format a list of capsules as a bullet list with title, category, tags, and ID."""
    capsules = data.get("capsules", [])
    total = data.get("total", len(capsules))

    if not capsules:
        return "No capsules found."

    lines = [f"Found {total} capsule{'s' if total != 1 else ''}:\n"]
    for c in capsules:
        title = c.get("title", "Untitled")
        category = c.get("category", "")
        tags = c.get("tags", [])
        capsule_id = c.get("id", "?")

        tag_str = f" [{', '.join(tags)}]" if tags else ""
        cat_str = f" ({category})" if category else ""
        lines.append(f"- **{title}**{cat_str}{tag_str} — ID: {capsule_id}")

    return "\n".join(lines)


def format_index(data: dict) -> str:
    """Format capsules grouped by category with counts."""
    capsules = data.get("capsules", [])

    if not capsules:
        return "No capsules in the knowledge base."

    by_category: dict[str, list[dict]] = defaultdict(list)
    for c in capsules:
        cat = c.get("category", "Uncategorized")
        by_category[cat].append(c)

    lines = [f"# Knowledge Index ({len(capsules)} total capsules)\n"]
    for cat in sorted(by_category.keys()):
        items = by_category[cat]
        count = len(items)
        plural = "s" if count != 1 else ""
        lines.append(f"## {cat} ({count} capsule{plural})")
        for c in items:
            title = c.get("title", "Untitled")
            capsule_id = c.get("id", "?")
            lines.append(f"  - {title} (ID: {capsule_id})")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="search_capsules",
        description=(
            "Search the user's personal knowledge base for relevant capsules. "
            "Capsules contain curated insights, techniques, prompts, workflows, and learnings. "
            "Uses semantic matching that finds conceptually related capsules."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Space-separated keywords (2-4 key concepts)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results (default: 10)",
                    "default": 10,
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
                "domain": {
                    "type": "string",
                    "description": "Optional domain filter",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_capsule",
        description="Get a specific capsule by its ID. Returns the full capsule content.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The capsule ID",
                },
            },
            "required": ["id"],
        },
    ),
    Tool(
        name="get_pinned",
        description=(
            "Get all pinned capsules (Eternal Truths). These represent the highest-priority "
            "knowledge. Read these early in a conversation to establish core values and principles."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
    Tool(
        name="get_index",
        description=(
            "Get the full knowledge index showing all capsules organized by category. "
            "Use this when you need to understand what knowledge is available."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
        },
    ),
]


# ---------------------------------------------------------------------------
# MCP Server handlers
# ---------------------------------------------------------------------------


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """Return available tools."""
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    """Dispatch tool calls to the appropriate handler."""
    arguments = arguments or {}
    client = get_client()

    try:
        if name == "search_capsules":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            filters = {}
            if arguments.get("category"):
                filters["category"] = arguments["category"]
            if arguments.get("domain"):
                filters["domain"] = arguments["domain"]
            data = await client.search_capsules(query=query, limit=limit, **filters)
            text = format_capsule_list(data)

        elif name == "get_capsule":
            capsule_id = arguments.get("id", "")
            data = await client.get_capsule(capsule_id)
            text = format_capsule(data)

        elif name == "get_pinned":
            data = await client.get_pinned()
            if not data.get("capsules"):
                text = "No pinned capsules found."
            else:
                text = format_capsule_list(data)

        elif name == "get_index":
            data = await client.get_index()
            text = format_index(data)

        else:
            text = f"Unknown tool: {name}"

    except Exception as e:
        text = f"Error calling {name}: {e}"

    return [TextContent(type="text", text=text)]


# ---------------------------------------------------------------------------
# Server runner
# ---------------------------------------------------------------------------


async def run_server():
    """Run the MCP server over stdio."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
