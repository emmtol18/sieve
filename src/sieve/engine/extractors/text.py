"""Plain text and markdown extractor."""

import json
from pathlib import Path
from typing import Optional

from .base import Extractor, ExtractedContent

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".rst", ".json"}


class TextExtractor(Extractor):
    """Extracts content from plain text files."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in TEXT_EXTENSIONS

    def extract(self, path: Path) -> ExtractedContent:
        """Extract text content."""
        text = path.read_text(encoding="utf-8", errors="ignore")

        # Handle JSON files specially (might be browser extension data)
        if path.suffix.lower() == ".json":
            return self._extract_json(text, path)

        # Try to extract title from first heading
        title = self._extract_title(text)

        return ExtractedContent(
            text=text,
            suggested_title=title or path.stem.replace("_", " ").replace("-", " ").title(),
        )

    def _extract_title(self, text: str) -> Optional[str]:
        """Extract title from first markdown heading."""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("## "):
                return line[3:].strip()
        return None

    def _extract_json(self, text: str, path: Path) -> ExtractedContent:
        """Extract content from JSON (browser extension format)."""
        try:
            data = json.loads(text)

            # Handle browser extension capture format
            if isinstance(data, dict):
                content = data.get("content", "")
                source_url = data.get("source_url") or data.get("url")
                title = data.get("title")

                return ExtractedContent(
                    text=content if content else json.dumps(data, indent=2),
                    source_url=source_url,
                    suggested_title=title,
                )

            return ExtractedContent(text=json.dumps(data, indent=2))
        except json.JSONDecodeError:
            return ExtractedContent(text=text)
