from sieve.mcp.server import format_capsule, format_capsule_list, format_index


def test_format_capsule():
    c = {
        "title": "Test",
        "category": "AI",
        "domain": "tech",
        "tags": ["ai"],
        "executive_summary": "Summary",
        "core_insight": "Insight",
        "full_content": "Content",
    }
    result = format_capsule(c)
    assert "# Test" in result
    assert "Summary" in result
    assert "Insight" in result
    assert "Content" in result
    assert "AI" in result


def test_format_capsule_minimal():
    c = {"title": "Minimal"}
    result = format_capsule(c)
    assert "# Minimal" in result


def test_format_capsule_list_empty():
    result = format_capsule_list({"capsules": [], "total": 0})
    assert "No capsules found" in result


def test_format_capsule_list():
    data = {
        "capsules": [
            {"id": "1", "title": "Test", "category": "AI", "tags": ["ai", "ml"]},
        ],
        "total": 1,
    }
    result = format_capsule_list(data)
    assert "Test" in result
    assert "AI" in result
    assert "1" in result


def test_format_capsule_list_multiple():
    data = {
        "capsules": [
            {"id": "1", "title": "First", "category": "AI", "tags": ["ai"]},
            {"id": "2", "title": "Second", "category": "Business", "tags": []},
        ],
        "total": 2,
    }
    result = format_capsule_list(data)
    assert "First" in result
    assert "Second" in result
    assert "2 capsules" in result


def test_format_index():
    data = {
        "capsules": [
            {"id": "1", "title": "Note A", "category": "AI"},
            {"id": "2", "title": "Note B", "category": "AI"},
            {"id": "3", "title": "Note C", "category": "Business"},
        ]
    }
    result = format_index(data)
    assert "AI (2 capsules)" in result
    assert "Business (1 capsule" in result
    assert "Note A" in result
    assert "Note B" in result
    assert "Note C" in result


def test_format_index_empty():
    data = {"capsules": []}
    result = format_index(data)
    assert "No capsules" in result or "empty" in result.lower() or "0" in result
