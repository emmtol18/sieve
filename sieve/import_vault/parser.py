import re

import yaml


MIN_CONTENT_LENGTH = 20


def parse_obsidian_note(content: str, filename: str) -> dict | None:
    """Parse an Obsidian markdown note into a structured dict.
    Returns None if the note is empty or too short.
    """
    if not content or len(content.strip()) < MIN_CONTENT_LENGTH:
        return None

    frontmatter = {}
    body = content
    has_metadata = False

    # Extract YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
            has_metadata = bool(frontmatter.get("tags"))
        except yaml.YAMLError:
            pass
        body = content[fm_match.end() :]

    title = _extract_title(body, filename)
    tags = frontmatter.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]

    return {
        "title": title,
        "full_content": body.strip(),
        "tags": tags,
        "has_metadata": has_metadata,
        "frontmatter": frontmatter,
        "filename": filename,
    }


def _extract_title(body: str, filename: str) -> str:
    h1_match = re.match(r"^#\s+(.+)$", body.strip(), re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()
    return re.sub(r"\.md$", "", filename).replace("-", " ").replace("_", " ").title()
