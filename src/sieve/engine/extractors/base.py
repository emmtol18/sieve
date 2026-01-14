"""Base extractor interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExtractedContent:
    """Content extracted from a file."""

    text: Optional[str] = None
    is_image: bool = False
    image_path: Optional[Path] = None
    source_url: Optional[str] = None
    suggested_title: Optional[str] = None


class Extractor(ABC):
    """Base class for content extractors."""

    @abstractmethod
    def can_handle(self, path: Path) -> bool:
        """Check if this extractor can handle the given file."""
        pass

    @abstractmethod
    def extract(self, path: Path) -> ExtractedContent:
        """Extract content from the file."""
        pass
