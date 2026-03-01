"""Migrate v1 Neural Sieve capsules (markdown + YAML frontmatter) to v3 cloud API."""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import frontmatter
import httpx

# Default location of v1 capsules
V1_CAPSULES_DIR = Path.home() / "Documents/Code/sieve_ideas/neural-sieve/Capsules"


def _extract_section(body: str, heading: str, next_headings: list[str]) -> str:
    """Extract text between a markdown heading and the next heading (or end of file).

    Args:
        body: The markdown body (without frontmatter).
        heading: The heading to extract content from (e.g. "Executive Summary").
        next_headings: List of possible next headings that terminate this section.

    Returns:
        The extracted text, stripped and with blockquote '> ' prefixes removed.
    """
    # Build pattern: match "# <heading>" then capture everything until the next heading or EOF
    next_pattern = "|".join(re.escape(h) for h in next_headings)
    if next_pattern:
        pattern = rf"^#\s+{re.escape(heading)}\s*\n(.*?)(?=^#\s+(?:{next_pattern})\s*$|\Z)"
    else:
        pattern = rf"^#\s+{re.escape(heading)}\s*\n(.*)"

    match = re.search(pattern, body, re.MULTILINE | re.DOTALL)
    if not match:
        return ""

    text = match.group(1).strip()

    # Strip blockquote '> ' prefix from each line
    lines = text.split("\n")
    stripped_lines = []
    for line in lines:
        if line.startswith("> "):
            stripped_lines.append(line[2:])
        elif line == ">":
            # Empty blockquote line
            stripped_lines.append("")
        else:
            stripped_lines.append(line)

    return "\n".join(stripped_lines).strip()


def parse_v1_capsule(content: str) -> dict:
    """Parse a v1 markdown capsule file and return a dict matching the v3 CapsuleCreate schema.

    Args:
        content: Raw markdown file content with YAML frontmatter.

    Returns:
        A dict with fields suitable for POSTing to the v3 /api/capsules/ endpoint.
    """
    post = frontmatter.loads(content)
    meta = post.metadata
    body = post.content

    # Extract sections from body
    executive_summary = _extract_section(
        body, "Executive Summary", ["Core Insight", "Full Content"]
    )
    core_insight = _extract_section(body, "Core Insight", ["Full Content"])
    full_content = _extract_section(body, "Full Content", [])

    return {
        # Content fields
        "title": meta.get("title", ""),
        "executive_summary": executive_summary,
        "core_insight": core_insight,
        "full_content": full_content,
        # Discovery metadata — from v1
        "tags": meta.get("tags", []),
        "category": meta.get("category", ""),
        # Discovery metadata — defaults (v1 doesn't have these)
        "keywords": [],
        "topics": [],
        "domain": "",
        "difficulty": "beginner",
        "content_type": "insight",
        # Provenance
        "author": "personal",
        "source_url": meta.get("source_url"),
        "capture_method": meta.get("capture_method", "manual"),
        "source_type": "",
        # System
        "status": meta.get("status", "active"),
        "pinned": meta.get("pinned", False),
        "skill_eligible": True,
    }


async def migrate(api_url: str, api_key: str) -> None:
    """Walk all v1 capsule .md files and POST each to the v3 API.

    Args:
        api_url: Base URL of the v3 API (e.g. "http://localhost:8000").
        api_key: API key for authentication.
    """
    capsules_dir = V1_CAPSULES_DIR
    if not capsules_dir.exists():
        print(f"Error: Capsules directory not found: {capsules_dir}")
        sys.exit(1)

    # Collect all .md files, skipping INDEX.md
    md_files: list[Path] = []
    for md_file in sorted(capsules_dir.rglob("*.md")):
        if md_file.name == "INDEX.md":
            continue
        md_files.append(md_file)

    total = len(md_files)
    print(f"Found {total} capsule files to migrate.")

    success = 0
    failed = 0
    errors: list[tuple[str, str]] = []

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, md_file in enumerate(md_files, start=1):
            relative = md_file.relative_to(capsules_dir)
            try:
                content = md_file.read_text(encoding="utf-8")
                capsule_data = parse_v1_capsule(content)

                response = await client.post(
                    f"{api_url}/api/capsules/",
                    json=capsule_data,
                    headers=headers,
                )
                response.raise_for_status()
                success += 1
                print(f"  [{i}/{total}] OK: {relative}")
            except Exception as exc:
                failed += 1
                error_msg = str(exc)
                errors.append((str(relative), error_msg))
                print(f"  [{i}/{total}] FAIL: {relative} — {error_msg}")

    print()
    print("=" * 60)
    print(f"Migration complete: {success} succeeded, {failed} failed out of {total}")
    if errors:
        print()
        print("Failures:")
        for path, err in errors:
            print(f"  - {path}: {err}")


def main() -> None:
    """CLI entry point for the migration script."""
    if len(sys.argv) < 3:
        print("Usage: uv run scripts/migrate_v1.py <API_URL> <API_KEY>")
        print("Example: uv run scripts/migrate_v1.py http://localhost:8000 my-api-key")
        sys.exit(1)

    api_url = sys.argv[1].rstrip("/")
    api_key = sys.argv[2]

    asyncio.run(migrate(api_url, api_key))


if __name__ == "__main__":
    main()
