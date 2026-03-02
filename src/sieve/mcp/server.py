"""MCP server for Neural Sieve — exposes capsule tools for Claude Code."""

import os
from collections import defaultdict

from mcp.server import Server
from mcp.types import TextContent, Tool
from sqlalchemy import select

from sieve.db.database import async_session
from sieve.db.models import Capsule, Sieve, User
from sieve.mcp.api_client import SieveAPIClient

server = Server("neural-sieve")


def _get_api_client() -> SieveAPIClient:
    """Create an API client from environment variables."""
    return SieveAPIClient(
        api_url=os.environ.get("SIEVE_API_URL", "http://localhost:8421"),
        api_key=os.environ.get("SIEVE_API_KEY", ""),
    )


async def _get_sieve_id():
    """Look up the sieve ID for the configured user email."""
    email = os.environ.get("SIEVE_USER_EMAIL", "")
    if not email:
        raise ValueError("SIEVE_USER_EMAIL environment variable is not set")

    async with async_session() as session:
        result = await session.execute(
            select(Sieve.id)
            .join(User, User.id == Sieve.user_id)
            .where(User.email == email)
        )
        sieve_id = result.scalar_one_or_none()
        if not sieve_id:
            raise ValueError(f"No sieve found for user {email}")
        return sieve_id


def _capsule_to_dict(c: Capsule) -> dict:
    """Convert a Capsule ORM model to a dict matching the format helpers."""
    return {
        "id": str(c.id),
        "title": c.title,
        "executive_summary": c.executive_summary,
        "core_insight": c.core_insight,
        "full_content": c.full_content,
        "tags": c.tags or [],
        "category": c.category or "",
        "domain": c.domain or "",
        "pinned": c.pinned,
    }


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


def format_skill(s: dict) -> str:
    """Format a skill as SKILL.md-compatible markdown."""
    lines = [
        "---",
        f"name: {s.get('name', 'unnamed')}",
        f"description: {s.get('description', '')}",
        "---",
        "",
        s.get("body", ""),
    ]
    return "\n".join(lines)


def format_skill_list(data: dict) -> str:
    """Format a list of skills as a bullet list."""
    skills = data.get("skills", [])
    total = data.get("total", len(skills))

    if not skills:
        return "No skills found."

    lines = [f"Found {total} skill{'s' if total != 1 else ''}:\n"]
    for s in skills:
        name = s.get("name", "unnamed")
        title = s.get("title", "Untitled")
        desc = s.get("description", "")[:100]
        skill_id = s.get("id", "?")
        lines.append(f"- **{title}** (`{name}`) — {desc} — ID: {skill_id}")

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
    Tool(
        name="search_skills",
        description=(
            "Search the user's skills. Skills are compiled from capsules and contain "
            "actionable knowledge formatted as Claude Code skills."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for skill name or description",
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
        name="get_skill",
        description="Get a specific skill by ID. Returns the full skill content as SKILL.md-compatible markdown.",
        inputSchema={
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The skill ID",
                },
            },
            "required": ["id"],
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

    try:
        sieve_id = await _get_sieve_id()

        if name == "search_capsules":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            category = arguments.get("category")
            domain = arguments.get("domain")

            async with async_session() as session:
                stmt = select(Capsule).where(Capsule.sieve_id == sieve_id)

                # ILIKE search across text fields
                if query:
                    pattern = f"%{query}%"
                    stmt = stmt.where(
                        Capsule.title.ilike(pattern)
                        | Capsule.executive_summary.ilike(pattern)
                        | Capsule.core_insight.ilike(pattern)
                        | Capsule.full_content.ilike(pattern)
                    )
                if category:
                    stmt = stmt.where(Capsule.category.ilike(f"%{category}%"))
                if domain:
                    stmt = stmt.where(Capsule.domain.ilike(f"%{domain}%"))

                stmt = stmt.limit(limit)
                result = await session.execute(stmt)
                capsules = [_capsule_to_dict(c) for c in result.scalars().all()]

            text = format_capsule_list({"capsules": capsules, "total": len(capsules)})

        elif name == "get_capsule":
            capsule_id = arguments.get("id", "")
            async with async_session() as session:
                result = await session.execute(
                    select(Capsule).where(
                        Capsule.id == capsule_id, Capsule.sieve_id == sieve_id
                    )
                )
                capsule = result.scalar_one_or_none()
                if not capsule:
                    text = f"Capsule {capsule_id} not found."
                else:
                    text = format_capsule(_capsule_to_dict(capsule))

        elif name == "get_pinned":
            async with async_session() as session:
                result = await session.execute(
                    select(Capsule).where(
                        Capsule.sieve_id == sieve_id, Capsule.pinned == True  # noqa: E712
                    )
                )
                capsules = [_capsule_to_dict(c) for c in result.scalars().all()]

            if not capsules:
                text = "No pinned capsules found."
            else:
                text = format_capsule_list({"capsules": capsules, "total": len(capsules)})

        elif name == "get_index":
            async with async_session() as session:
                result = await session.execute(
                    select(Capsule)
                    .where(Capsule.sieve_id == sieve_id)
                    .order_by(Capsule.category, Capsule.created_at.desc())
                )
                capsules = [_capsule_to_dict(c) for c in result.scalars().all()]

            text = format_index({"capsules": capsules})

        elif name == "search_skills":
            query = arguments.get("query", "")
            limit = arguments.get("limit", 10)
            api_client = _get_api_client()
            data = await api_client.list_skills(search=query, limit=limit)
            text = format_skill_list(data)

        elif name == "get_skill":
            skill_id = arguments.get("id", "")
            api_client = _get_api_client()
            data = await api_client.get_skill(skill_id)
            text = format_skill(data)

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
