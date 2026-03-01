import logging
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Hostnames and IPs that must be blocked to prevent SSRF attacks
BLOCKED_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "169.254.169.254",
        "metadata.google.internal",
    }
)

ALLOWED_SCHEMES = frozenset({"http", "https"})

# HTML tags to strip when extracting text content
STRIP_TAGS = frozenset({"script", "style", "nav", "footer", "header", "aside"})


def validate_url(url: str) -> str:
    """Validate a URL for safety (SSRF protection).

    Blocks:
    - localhost, 127.0.0.1, 0.0.0.0, 169.254.169.254, metadata.google.internal
    - Non-http(s) schemes (ftp, file, etc.)

    Returns the validated URL string.
    Raises ValueError if the URL is blocked.
    """
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(f"URL scheme '{parsed.scheme}' is not allowed. Only http and https are permitted.")

    # Extract hostname without port
    hostname = parsed.hostname or ""

    if hostname in BLOCKED_HOSTS:
        raise ValueError(f"URL host '{hostname}' is blocked for security reasons.")

    # Block private IP ranges starting with 169.254
    if hostname.startswith("169.254."):
        raise ValueError(f"URL host '{hostname}' is blocked (link-local address).")

    return url


async def fetch_url(url: str) -> str:
    """Fetch the HTML content of a URL.

    Validates the URL for SSRF safety, then fetches with a 30s timeout.
    Follows redirects.

    Returns the HTML content as a string.
    Raises ValueError for blocked URLs.
    Raises httpx.HTTPError for network errors.
    """
    validated_url = validate_url(url)

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        response = await client.get(validated_url)
        response.raise_for_status()
        return response.text


def extract_text_from_html(html: str) -> str:
    """Extract readable text content from HTML.

    Strips script, style, nav, footer, header, and aside tags.
    Returns cleaned text with normalized whitespace.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove unwanted tags
    for tag in soup.find_all(STRIP_TAGS):
        tag.decompose()

    # Extract text with space separator and normalize whitespace
    text = soup.get_text(separator=" ", strip=True)

    # Collapse multiple whitespace
    return " ".join(text.split())
