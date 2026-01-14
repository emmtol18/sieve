"""Image file extractor."""

from pathlib import Path

from .base import Extractor, ExtractedContent

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"}


class ImageExtractor(Extractor):
    """Extracts content from image files (handled by LLM vision)."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in IMAGE_EXTENSIONS

    def extract(self, path: Path) -> ExtractedContent:
        """Return image path for LLM vision processing."""
        return ExtractedContent(
            is_image=True,
            image_path=path,
            suggested_title=path.stem.replace("_", " ").replace("-", " ").title(),
        )
