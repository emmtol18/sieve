"""Pydantic models for Knowledge Capsules."""

from datetime import date, datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class CapsuleMetadata(BaseModel):
    """YAML frontmatter for a capsule."""

    id: str = Field(description="Unique identifier, e.g. 2026-01-14-T1000")
    title: str
    source_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    category: str = "Uncategorized"
    status: str = "active"  # active, legacy
    pinned: bool = False
    captured_at: date = Field(default_factory=date.today)
    capture_method: str = "manual"  # manual, screenshot, browser, drop
    original_asset: Optional[str] = None  # Relative path to original file

    def to_frontmatter(self) -> dict:
        """Convert to YAML-serializable dict."""
        return {
            "id": self.id,
            "title": self.title,
            "source_url": self.source_url,
            "tags": self.tags,
            "category": self.category,
            "status": self.status,
            "pinned": self.pinned,
            "captured_at": self.captured_at.isoformat(),
            "capture_method": self.capture_method,
            "original_asset": self.original_asset,
        }


class Capsule(BaseModel):
    """Complete capsule with metadata and content."""

    metadata: CapsuleMetadata
    executive_summary: str = Field(description="2-sentence hook for AI comprehension")
    core_insight: str = Field(description="The main 'Aha!' moment")
    full_content: str = Field(description="Complete cleaned text")

    @property
    def filename(self) -> str:
        """Generate filename from metadata."""
        slug = self.metadata.title.lower()
        slug = "".join(c if c.isalnum() or c == " " else "" for c in slug)
        slug = "_".join(slug.split()[:6])
        date_prefix = self.metadata.captured_at.strftime("%Y%m%d")
        return f"{date_prefix}_{slug}.md"

    def to_markdown(self) -> str:
        """Render capsule as markdown with YAML frontmatter."""
        import yaml

        frontmatter = yaml.dump(
            self.metadata.to_frontmatter(),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

        return f"""---
{frontmatter.strip()}
---

# Executive Summary

> {self.executive_summary}

# Core Insight

{self.core_insight}

# Full Content

{self.full_content}
"""


class CapsuleInput(BaseModel):
    """Input data for capsule creation (from browser extension or file)."""

    content: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    capture_method: str = "manual"
    image_data: Optional[str] = None  # Base64 encoded image
