"""Capsule file writer."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

from ..config import Settings
from ..utils import get_unique_path
from .loader import find_by_source_url
from .schema import Capsule

logger = logging.getLogger(__name__)


class CapsuleWriter:
    """Writes capsules to disk and manages assets."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def write(self, capsule: Capsule, original_file: Path | None = None) -> Path:
        """Write capsule to disk and copy original asset if provided.

        If a capsule with the same source_url already exists, merges the content.

        Returns the path to the created/updated capsule file.
        """
        # Check for existing capsule with same source_url
        if capsule.metadata.source_url:
            existing = find_by_source_url(self.settings, capsule.metadata.source_url)
            if existing:
                return self._merge_capsule(existing, capsule, original_file)

        # Ensure category directory exists
        category_dir = self.settings.capsules_path / capsule.metadata.category
        category_dir.mkdir(parents=True, exist_ok=True)

        # Write capsule markdown
        capsule_path = category_dir / capsule.filename
        capsule_path.write_text(capsule.to_markdown(), encoding="utf-8")

        # Copy original asset if provided
        if original_file and original_file.exists():
            asset_path = self._copy_asset(original_file)
            # Update capsule with relative asset path
            rel_path = asset_path.relative_to(self.settings.vault_root)
            capsule.metadata.original_asset = str(rel_path)
            # Rewrite with updated asset path
            capsule_path.write_text(capsule.to_markdown(), encoding="utf-8")

        return capsule_path

    def _copy_asset(self, source: Path) -> Path:
        """Copy original file to Assets folder, organized by month."""
        month_dir = self.settings.assets_path / datetime.now().strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)

        dest = get_unique_path(month_dir / source.name)
        shutil.copy2(source, dest)
        return dest

    def _merge_capsule(
        self,
        existing: tuple[Path, dict],
        new_capsule: Capsule,
        original_file: Path | None = None,
    ) -> Path:
        """Merge new capsule content into an existing capsule with same source_url.

        Appends new full_content with separator, merges tags (unique).
        """
        existing_path, existing_data = existing
        existing_content = existing_data["content"]
        existing_meta = existing_data["metadata"]

        logger.info(f"[WRITER] Merging duplicate URL into: {existing_path.name}")

        # Parse existing content sections
        sections = self._parse_sections(existing_content)

        # Append new content to full_content section with separator
        new_full_content = new_capsule.full_content.strip()
        if new_full_content:
            existing_full = sections.get("full_content", "").strip()
            if existing_full:
                # Add separator and new content
                merged_full = f"{existing_full}\n\n---\n\n{new_full_content}"
            else:
                merged_full = new_full_content
            sections["full_content"] = merged_full

        # Merge tags (unique, preserving order)
        existing_tags = existing_meta.get("tags", []) or []
        new_tags = new_capsule.metadata.tags or []
        merged_tags = list(existing_tags)
        for tag in new_tags:
            if tag not in merged_tags:
                merged_tags.append(tag)
        existing_meta["tags"] = merged_tags

        # Build merged markdown
        import yaml

        frontmatter = yaml.dump(
            existing_meta,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        merged_md = f"""---
{frontmatter.strip()}
---

# Executive Summary

> {sections.get("executive_summary", new_capsule.executive_summary)}

# Core Insight

{sections.get("core_insight", new_capsule.core_insight)}

# Full Content

{sections["full_content"]}
"""

        # Write merged content
        existing_path.write_text(merged_md, encoding="utf-8")

        # Copy asset if provided
        if original_file and original_file.exists():
            self._copy_asset(original_file)

        return existing_path

    def _parse_sections(self, content: str) -> dict[str, str]:
        """Parse markdown content into sections."""
        sections = {}
        current_section = None
        current_content = []

        for line in content.split("\n"):
            if line.startswith("# Executive Summary"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "executive_summary"
                current_content = []
            elif line.startswith("# Core Insight"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "core_insight"
                current_content = []
            elif line.startswith("# Full Content"):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "full_content"
                current_content = []
            else:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        # Clean up executive summary (remove leading >)
        if "executive_summary" in sections:
            summary = sections["executive_summary"]
            if summary.startswith(">"):
                sections["executive_summary"] = summary[1:].strip()

        return sections

    def move_to_legacy(self, capsule_path: Path) -> Path:
        """Move a capsule to the Legacy folder."""
        self.settings.legacy_path.mkdir(parents=True, exist_ok=True)
        dest = get_unique_path(self.settings.legacy_path / capsule_path.name)
        shutil.move(capsule_path, dest)
        return dest
