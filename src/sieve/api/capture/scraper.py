import ipaddress
import logging
import socket
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

MAX_REDIRECTS = 5


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private, loopback, link-local, or reserved."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # If we can't parse it, block it
    return addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast


def validate_url(url: str) -> str:
    """Validate a URL for safety (SSRF protection).

    Blocks:
    - Private/reserved/loopback/link-local/multicast IPs
    - Known cloud metadata hostnames
    - Non-http(s) schemes (ftp, file, etc.)

    Also resolves DNS to check the actual IP target.

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

    # Resolve DNS and check the actual IP
    try:
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname '{hostname}'.")

    for family, _, _, _, sockaddr in resolved_ips:
        ip_str = sockaddr[0]
        if _is_private_ip(ip_str):
            raise ValueError(f"URL host '{hostname}' resolves to a private/reserved address.")

    return url


async def fetch_url(url: str) -> str:
    """Fetch the HTML content of a URL.

    Validates the URL for SSRF safety, then fetches with a 30s timeout.
    Follows redirects manually, re-validating each redirect target.

    Returns the HTML content as a string.
    Raises ValueError for blocked URLs.
    Raises httpx.HTTPError for network errors.
    """
    validated_url = validate_url(url)

    async with httpx.AsyncClient(follow_redirects=False, timeout=30.0) as client:
        for _ in range(MAX_REDIRECTS):
            response = await client.get(validated_url)
            if response.is_redirect:
                redirect_url = str(response.next_request.url) if response.next_request else None
                if not redirect_url:
                    break
                validated_url = validate_url(redirect_url)
                continue
            response.raise_for_status()
            return response.text

    raise ValueError("Too many redirects.")


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
