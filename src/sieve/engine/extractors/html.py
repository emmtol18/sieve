"""HTML content extractor."""

from pathlib import Path

from bs4 import BeautifulSoup

from .base import Extractor, ExtractedContent


class HTMLExtractor(Extractor):
    """Extracts clean text from HTML files."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in {".html", ".htm"}

    def extract(self, path: Path) -> ExtractedContent:
        """Extract article content from HTML."""
        html = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "lxml")

        # Remove noise elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # Try to find article content
        article = (
            soup.find("article")
            or soup.find("main")
            or soup.find(role="main")
            or soup.find(class_="content")
            or soup.find(id="content")
        )

        content_elem = article if article else soup.body
        text = content_elem.get_text(separator="\n", strip=True) if content_elem else ""

        # Get title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Try to find source URL in meta tags
        canonical = soup.find("link", rel="canonical")
        og_url = soup.find("meta", property="og:url")
        source_url = None
        if canonical and canonical.get("href"):
            source_url = canonical["href"]
        elif og_url and og_url.get("content"):
            source_url = og_url["content"]

        return ExtractedContent(
            text=text,
            source_url=source_url,
            suggested_title=title,
        )
