import pytest

from sieve.api.capture.scraper import validate_url, extract_text_from_html


def test_validate_url_blocks_localhost():
    with pytest.raises(ValueError):
        validate_url("http://localhost/secret")


def test_validate_url_blocks_localhost_with_port():
    with pytest.raises(ValueError):
        validate_url("http://localhost:8080/secret")


def test_validate_url_blocks_127():
    with pytest.raises(ValueError):
        validate_url("http://127.0.0.1/admin")


def test_validate_url_blocks_metadata():
    with pytest.raises(ValueError):
        validate_url("http://169.254.169.254/latest/meta-data/")


def test_validate_url_blocks_google_metadata():
    with pytest.raises(ValueError):
        validate_url("http://metadata.google.internal/computeMetadata/v1/")


def test_validate_url_blocks_zero_ip():
    with pytest.raises(ValueError):
        validate_url("http://0.0.0.0/secret")


def test_validate_url_blocks_ftp():
    with pytest.raises(ValueError):
        validate_url("ftp://example.com/file")


def test_validate_url_blocks_file_scheme():
    with pytest.raises(ValueError):
        validate_url("file:///etc/passwd")


def test_validate_url_allows_https():
    assert validate_url("https://example.com") == "https://example.com"


def test_validate_url_allows_http():
    assert validate_url("http://example.com") == "http://example.com"


def test_validate_url_allows_path():
    result = validate_url("https://example.com/path/to/page")
    assert result == "https://example.com/path/to/page"


def test_extract_text_strips_scripts():
    html = "<html><body><script>alert(1)</script><p>Hello</p></body></html>"
    text = extract_text_from_html(html)
    assert "alert" not in text
    assert "Hello" in text


def test_extract_text_strips_style():
    html = "<html><body><style>.red{color:red}</style><p>World</p></body></html>"
    text = extract_text_from_html(html)
    assert "red" not in text
    assert "World" in text


def test_extract_text_strips_nav_footer_header_aside():
    html = """
    <html><body>
        <nav>Navigation</nav>
        <header>Header</header>
        <main><p>Main Content</p></main>
        <aside>Sidebar</aside>
        <footer>Footer</footer>
    </body></html>
    """
    text = extract_text_from_html(html)
    assert "Navigation" not in text
    assert "Header" not in text
    assert "Sidebar" not in text
    assert "Footer" not in text
    assert "Main Content" in text


def test_extract_text_handles_empty_html():
    text = extract_text_from_html("")
    assert text == ""


def test_extract_text_handles_plain_text():
    html = "<html><body><p>Just some text</p></body></html>"
    text = extract_text_from_html(html)
    assert "Just some text" in text
