from sieve.import_vault.parser import parse_obsidian_note


def test_parse_note_with_frontmatter():
    content = (
        "---\ntags:\n  - ai\n  - machine-learning\n---\n\n"
        "# Machine Learning Fundamentals\n\n"
        "Key concepts in ML include supervised and unsupervised learning."
    )
    result = parse_obsidian_note(content, "ml-basics.md")
    assert result is not None
    assert result["tags"] == ["ai", "machine-learning"]
    assert "Machine Learning Fundamentals" in result["title"]
    assert result["has_metadata"] is True


def test_parse_note_without_frontmatter():
    content = "# Quick Thought\n\nSome interesting idea about design patterns and architecture."
    result = parse_obsidian_note(content, "quick-thought.md")
    assert result is not None
    assert result["title"] == "Quick Thought"
    assert result["has_metadata"] is False


def test_parse_empty_note():
    assert parse_obsidian_note("", "empty.md") is None


def test_parse_short_note():
    assert parse_obsidian_note("hi", "short.md") is None


def test_parse_note_title_from_filename():
    content = "This is a longer note without any heading but has enough content to parse."
    result = parse_obsidian_note(content, "my-cool-note.md")
    assert result is not None
    assert result["title"] == "My Cool Note"
    assert result["filename"] == "my-cool-note.md"


def test_parse_note_with_comma_separated_tags():
    content = "---\ntags: ai, ml, deep-learning\n---\n\nSome detailed content about deep learning techniques and methods."
    result = parse_obsidian_note(content, "dl.md")
    assert result is not None
    assert result["tags"] == ["ai", "ml", "deep-learning"]
    assert result["has_metadata"] is True


def test_parse_note_with_invalid_yaml():
    content = "---\n: invalid yaml [[\n---\n\nSome content that is long enough to be valid for parsing."
    result = parse_obsidian_note(content, "bad-yaml.md")
    assert result is not None
    assert result["frontmatter"] == {}
    assert result["has_metadata"] is False
