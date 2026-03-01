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
    """Protected dashboard routes call _is_authenticated."""
    import inspect
    from sieve.dashboard.routes import sieve_page, capture_page, discover_page, compile_page, capsule_detail

    for fn in [sieve_page, capture_page, discover_page, compile_page, capsule_detail]:
        source = inspect.getsource(fn)
        assert "_is_authenticated" in source, f"{fn.__name__} missing auth check"
