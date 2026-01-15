"""Knowledge index regeneration."""

import logging
from collections import defaultdict
from datetime import datetime

from ..capsule import load_capsules
from ..config import Settings

logger = logging.getLogger(__name__)


class Indexer:
    """Regenerates the knowledge index from capsules."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def regenerate(self):
        """Regenerate the knowledge index."""
        capsules = load_capsules(self.settings)

        # Group by category and separate pinned
        pinned = []
        by_category = defaultdict(list)

        for capsule in capsules:
            if capsule.get("pinned"):
                pinned.append(capsule)
            by_category[capsule.get("category", "Uncategorized")].append(capsule)

        # Generate markdown
        content = self._generate_markdown(pinned, by_category)

        # Write index
        self.settings.index_path.write_text(content, encoding="utf-8")
        logger.info("INDEX.md regenerated")

    def _generate_markdown(
        self, pinned: list[dict], by_category: dict[str, list[dict]]
    ) -> str:
        """Generate README markdown content."""
        lines = [
            "# Neural Sieve",
            "",
            "> The High-Signal External Memory for AI Influence",
            "",
            f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "",
        ]

        # Pinned section
        if pinned:
            lines.extend([
                "## Eternal Truths",
                "",
                "*Pinned capsules - highest priority context*",
                "",
            ])
            for capsule in pinned:
                lines.append(self._format_capsule_line(capsule))
            lines.append("")

        # Categories
        lines.append("## Knowledge Map")
        lines.append("")

        # Sort categories alphabetically
        for category in sorted(by_category.keys()):
            capsules = by_category[category]
            lines.append(f"### {category}")
            lines.append("")
            for capsule in capsules[:20]:  # Limit per category
                lines.append(self._format_capsule_line(capsule))
            if len(capsules) > 20:
                lines.append(f"  *...and {len(capsules) - 20} more*")
            lines.append("")

        # Stats
        total = sum(len(c) for c in by_category.values())
        lines.extend([
            "---",
            "",
            f"**Total capsules:** {total} | **Categories:** {len(by_category)} | **Pinned:** {len(pinned)}",
            "",
        ])

        return "\n".join(lines)

    def _format_capsule_line(self, capsule: dict) -> str:
        """Format a single capsule as a markdown line."""
        title = capsule.get("title", "Untitled")
        path = capsule.get("_path", "")
        tags = capsule.get("tags", [])
        pin_marker = " [pinned]" if capsule.get("pinned") else ""

        # Adjust path: INDEX.md is inside Capsules/, so remove "Capsules/" prefix
        if path.startswith("Capsules/"):
            path = path[9:]  # Remove "Capsules/" prefix

        tag_str = f" `{'` `'.join(tags)}`" if tags else ""

        return f"- [{title}]({path}){pin_marker}{tag_str}"
