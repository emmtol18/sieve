"""Shared utility functions for the sieve package."""

from urllib.parse import urlparse


def escape_like(value: str) -> str:
    """Escape special LIKE/ILIKE characters."""
    return value.replace("%", "\\%").replace("_", "\\_")


def extract_domain(url: str | None) -> str:
    """Extract domain from a URL, e.g. 'https://example.com/path' -> 'example.com'."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return parsed.netloc or ""
    except Exception:
        return ""
