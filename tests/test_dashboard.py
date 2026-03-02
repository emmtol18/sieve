from pathlib import Path


def test_dashboard_routes_exist():
    from sieve.dashboard.routes import router

    paths = [r.path for r in router.routes]
    assert "/" in paths
    assert "/sieve" in paths
    assert "/capture" in paths
    assert "/discover" in paths
    assert "/compile" in paths
    assert "/login" in paths
    assert "/capsule/{capsule_id}" in paths


def test_templates_directory_exists():
    templates_dir = Path("src/sieve/dashboard/templates")
    assert templates_dir.exists()


def test_static_directory_exists():
    static_dir = Path("src/sieve/dashboard/static")
    assert static_dir.exists()


def test_all_templates_exist():
    templates_dir = Path("src/sieve/dashboard/templates")
    expected = ["base.html", "sieve.html", "capture.html", "discover.html",
                "compile.html", "capsule_detail.html", "login.html"]
    for name in expected:
        assert (templates_dir / name).exists(), f"Template {name} is missing"


def test_static_files_exist():
    static_dir = Path("src/sieve/dashboard/static")
    assert (static_dir / "style.css").exists()
    assert (static_dir / "manifest.json").exists()


def test_manifest_json_valid():
    import json

    manifest_path = Path("src/sieve/dashboard/static/manifest.json")
    data = json.loads(manifest_path.read_text())
    assert data["name"] == "Neural Sieve"
    assert data["short_name"] == "Sieve"
    assert data["theme_color"] == "#6366f1"
    assert data["background_color"] == "#0a0a0a"


def test_style_css_has_dark_theme():
    css = Path("src/sieve/dashboard/static/style.css").read_text()
    assert "#0a0a0a" in css  # Background
    assert "#141414" in css  # Card background
    assert "#6366f1" in css  # Accent
    assert "#e5e5e5" in css  # Text color


def test_base_template_has_htmx():
    html = Path("src/sieve/dashboard/templates/base.html").read_text()
    assert "htmx.org" in html
    assert "hx-boost" in html
    assert "manifest.json" in html


def test_sieve_template_has_search():
    html = Path("src/sieve/dashboard/templates/sieve.html").read_text()
    assert "hx-get" in html
    assert "hx-trigger" in html
    assert "delay:" in html  # debounced search


def test_capture_template_has_form():
    html = Path("src/sieve/dashboard/templates/capture.html").read_text()
    assert "hx-post" in html
    assert "hx-target" in html
    assert "textarea" in html.lower()


def test_login_template_has_tabs():
    html = Path("src/sieve/dashboard/templates/login.html").read_text()
    assert "Sign In" in html
    assert "Sign Up" in html
    assert "hx-post" in html


def test_protected_routes_have_auth_check():
    """Protected dashboard routes use the _protected auth guard."""
    import inspect
    from sieve.dashboard.routes import sieve_page, capture_page, discover_page, compile_page, capsule_detail

    for fn in [sieve_page, capture_page, discover_page, compile_page, capsule_detail]:
        source = inspect.getsource(fn)
        assert "_protected" in source, f"{fn.__name__} missing auth check"


# ---------------------------------------------------------------------------
# Social dashboard template tests (Tasks 8-12)
# ---------------------------------------------------------------------------


def test_feed_template_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/feed.html")


def test_feed_card_partial_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/partials/feed_card.html")


def test_discover_template_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/discover.html")


def test_sieve_card_partial_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/partials/sieve_card.html")


def test_profile_template_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/profile.html")


def test_settings_template_exists():
    import os
    assert os.path.exists("src/sieve/dashboard/templates/settings.html")


def test_base_template_has_feed_nav():
    with open("src/sieve/dashboard/templates/base.html") as f:
        content = f.read()
    assert 'href="/"' in content or '/' in content
    assert '/discover' in content
    assert '/capture' in content


def test_css_has_bottom_nav():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".bottom-nav" in content


def test_css_has_feed_card():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".feed-card" in content


def test_css_has_sieve_card():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".sieve-card" in content


def test_css_has_follow_btn():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".follow-btn" in content


def test_css_has_profile_header():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".profile-header" in content


def test_css_has_tag_pill():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".tag-pill" in content


def test_css_has_feed_filters():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".feed-filters" in content


def test_css_has_quick_capture():
    with open("src/sieve/dashboard/static/style.css") as f:
        content = f.read()
    assert ".quick-capture" in content


def test_feed_template_has_htmx():
    html = Path("src/sieve/dashboard/templates/feed.html").read_text()
    assert "hx-get" in html
    assert "hx-post" in html
    assert "/htmx/feed/" in html
    assert "/htmx/capture/" in html


def test_discover_template_has_htmx():
    html = Path("src/sieve/dashboard/templates/discover.html").read_text()
    assert "hx-get" in html
    assert "/htmx/discover/sieves" in html
    assert "/htmx/discover/capsules" in html


def test_settings_template_has_form():
    html = Path("src/sieve/dashboard/templates/settings.html").read_text()
    assert "hx-put" in html
    assert "/htmx/sieves/me" in html
    assert "api-key-input" in html


def test_profile_template_has_stats():
    html = Path("src/sieve/dashboard/templates/profile.html").read_text()
    assert "profile-stats" in html
    assert "follow-btn" in html


def test_base_template_has_bottom_nav():
    html = Path("src/sieve/dashboard/templates/base.html").read_text()
    assert "bottom-nav" in html
    assert "/settings" in html


def test_dashboard_routes_include_new_pages():
    from sieve.dashboard.routes import router

    paths = [r.path for r in router.routes]
    assert "/settings" in paths
    assert "/sieve/@{username}" in paths


# ---------------------------------------------------------------------------
# Import page tests (Tasks 17-19)
# ---------------------------------------------------------------------------


def test_import_template_exists():
    import os

    assert os.path.exists("src/sieve/dashboard/templates/import.html")


def test_import_template_has_upload_form():
    html = Path("src/sieve/dashboard/templates/import.html").read_text()
    assert "hx-post" in html
    assert "multipart/form-data" in html
    assert "drop-zone" in html
    assert 'accept=".zip"' in html


def test_import_route_exists():
    from sieve.dashboard.routes import router

    paths = [r.path for r in router.routes]
    assert "/import" in paths


def test_css_has_drop_zone():
    css = Path("src/sieve/dashboard/static/style.css").read_text()
    assert ".drop-zone" in css
    assert ".dragover" in css
