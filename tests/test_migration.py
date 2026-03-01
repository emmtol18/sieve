from scripts.migrate_v1 import parse_v1_capsule


def test_parse_v1_capsule():
    v1_content = '''---
id: 2026-01-22-T095249-3306
title: AI Agent Unlocks Paid Data
source_url: https://example.com
tags:
- AI agents
- Data access
category: AI Agents
status: active
pinned: false
captured_at: '2026-01-22'
capture_method: browser
---

# Executive Summary

> Test summary.

# Core Insight

Test insight.

# Full Content

Full content here.
'''
    result = parse_v1_capsule(v1_content)
    assert result["title"] == "AI Agent Unlocks Paid Data"
    assert "AI agents" in result["tags"]
    assert result["executive_summary"] == "Test summary."
    assert result["core_insight"] == "Test insight."
    assert result["full_content"] == "Full content here."
    assert result["author"] == "personal"
    assert result["category"] == "AI Agents"
    assert result["source_url"] == "https://example.com"
    assert result["capture_method"] == "browser"
    assert result["status"] == "active"
    assert result["pinned"] is False
    assert result["skill_eligible"] is True


def test_parse_v1_capsule_without_blockquote():
    v1_content = '''---
title: Simple Note
tags: [test]
category: Test
status: active
pinned: true
captured_at: '2026-02-01'
capture_method: manual
---

# Executive Summary

No blockquote here.

# Core Insight

Simple insight.

# Full Content

Simple content.
'''
    result = parse_v1_capsule(v1_content)
    assert result["executive_summary"] == "No blockquote here."
    assert result["pinned"] is True


def test_parse_v1_capsule_multiline_sections():
    v1_content = '''---
title: Multi-line Test
tags:
- tag1
- tag2
category: Testing
status: active
pinned: false
captured_at: '2026-01-15'
capture_method: browser
---

# Executive Summary

> First line of summary.
> Second line of summary.

# Core Insight

First line of insight.
Second line of insight.

# Full Content

First paragraph.

Second paragraph with more details.
'''
    result = parse_v1_capsule(v1_content)
    assert "First line of summary." in result["executive_summary"]
    assert "Second line of summary." in result["executive_summary"]
    assert "First line of insight." in result["core_insight"]
    assert "Second line of insight." in result["core_insight"]
    assert "First paragraph." in result["full_content"]
    assert "Second paragraph" in result["full_content"]


def test_parse_v1_capsule_defaults_for_missing_fields():
    v1_content = '''---
title: Minimal Capsule
tags: []
category: General
status: active
pinned: false
captured_at: '2026-01-10'
capture_method: manual
---

# Executive Summary

Summary.

# Core Insight

Insight.

# Full Content

Content.
'''
    result = parse_v1_capsule(v1_content)
    assert result["keywords"] == []
    assert result["topics"] == []
    assert result["domain"] == ""
    assert result["difficulty"] == "beginner"
    assert result["content_type"] == "insight"
    assert result["source_type"] == ""
    assert result["author"] == "personal"
    assert result["skill_eligible"] is True


def test_parse_v1_capsule_preserves_source_url_none():
    v1_content = '''---
title: No Source
tags: []
category: General
status: active
pinned: false
captured_at: '2026-01-10'
capture_method: manual
---

# Executive Summary

Summary.

# Core Insight

Insight.

# Full Content

Content.
'''
    result = parse_v1_capsule(v1_content)
    assert result["source_url"] is None


def test_parse_v1_capsule_original_asset_null():
    """original_asset is a v1-only field that should not appear in v3 output."""
    v1_content = '''---
title: With Asset
tags: []
category: General
status: active
pinned: false
captured_at: '2026-01-10'
capture_method: browser
original_asset: null
---

# Executive Summary

Summary.

# Core Insight

Insight.

# Full Content

Content.
'''
    result = parse_v1_capsule(v1_content)
    # original_asset is not a v3 field
    assert "original_asset" not in result
