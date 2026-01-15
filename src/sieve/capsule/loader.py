"""Capsule loading utilities."""

from pathlib import Path

import frontmatter

from ..config import Settings


def load_capsules(
    settings: Settings,
    include_content: bool = False,
    include_legacy: bool = False,
) -> list[dict]:
    """Load capsules from the Capsules/ directory.

    Args:
        settings: Application settings with vault paths
        include_content: Whether to include the full markdown content
        include_legacy: Whether to include capsules with status='legacy'

    Returns:
        List of capsule metadata dictionaries, sorted by captured_at (newest first)
    """
    capsules = []
    capsules_dir = settings.capsules_path

    if not capsules_dir.exists():
        return capsules

    for md_file in capsules_dir.rglob("*.md"):
        try:
            post = frontmatter.load(md_file)
            capsule = dict(post.metadata)

            # Skip legacy capsules unless requested
            if not include_legacy and capsule.get("status") == "legacy":
                continue

            # Add path metadata
            capsule["_path"] = str(md_file.relative_to(settings.vault_root))
            capsule["_filename"] = md_file.name
            capsule["_absolute_path"] = str(md_file)

            if include_content:
                capsule["_content"] = post.content

            capsules.append(capsule)
        except Exception:
            # Skip files that cannot be parsed
            pass

    return sorted(capsules, key=lambda c: c.get("captured_at", ""), reverse=True)


def find_capsule_file(settings: Settings, filename: str) -> Path | None:
    """Find a capsule file by filename.

    Args:
        settings: Application settings with vault paths
        filename: The filename to search for

    Returns:
        Path to the capsule file, or None if not found

    Security:
        - Rejects filenames containing path separators to prevent traversal
        - Validates resolved path is within capsules directory
    """
    # Security: reject filenames with path separators
    if "/" in filename or "\\" in filename or ".." in filename:
        return None

    # Security: only allow .md files
    if not filename.endswith(".md"):
        return None

    capsules_root = settings.capsules_path.resolve()

    for md_file in capsules_root.rglob("*.md"):
        if md_file.name == filename:
            # Security: verify file is within capsules directory
            try:
                md_file.resolve().relative_to(capsules_root)
                return md_file
            except ValueError:
                # Path is outside capsules directory
                return None
    return None
