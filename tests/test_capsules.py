import uuid

from sieve.api.capsules.schemas import CapsuleCreate, CapsuleResponse, CapsuleUpdate, CapsuleListResponse, CaptureRequest, SearchRequest


def test_capsule_create_schema():
    data = CapsuleCreate(
        title="Test",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        tags=["ai"],
        keywords=["artificial-intelligence"],
        topics=["technology"],
        category="AI",
        domain="technology",
    )
    assert data.title == "Test"
    assert data.tags == ["ai"]


def test_capsule_create_defaults():
    data = CapsuleCreate(title="Minimal")
    assert data.executive_summary == ""
    assert data.core_insight == ""
    assert data.full_content == ""
    assert data.tags == []
    assert data.keywords == []
    assert data.topics == []
    assert data.category == ""
    assert data.domain == ""
    assert data.difficulty == "beginner"
    assert data.content_type == "insight"
    assert data.author == "personal"
    assert data.source_url is None
    assert data.capture_method == "manual"
    assert data.source_type == ""
    assert data.pinned is False
    assert data.skill_eligible is True


def test_capsule_update_schema():
    data = CapsuleUpdate(title="Updated Title", pinned=True)
    assert data.title == "Updated Title"
    assert data.pinned is True
    assert data.executive_summary is None
    assert data.status is None


def test_capsule_response_schema():
    resp = CapsuleResponse(
        id=str(uuid.uuid4()),
        title="Test",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        tags=["ai"],
        keywords=["artificial-intelligence"],
        topics=["technology"],
        category="AI",
        domain="technology",
        difficulty="beginner",
        content_type="insight",
        author="personal",
        source_url=None,
        capture_method="manual",
        source_type="blog",
        status="active",
        pinned=False,
        skill_eligible=True,
        created_at="2026-03-01T00:00:00",
    )
    assert resp.title == "Test"
    assert resp.status == "active"
    assert resp.source_url is None


def test_capsule_list_response_schema():
    capsule = CapsuleResponse(
        id=str(uuid.uuid4()),
        title="Test",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
        tags=[],
        keywords=[],
        topics=[],
        category="",
        domain="",
        difficulty="beginner",
        content_type="insight",
        author="personal",
        source_url=None,
        capture_method="manual",
        source_type="",
        status="active",
        pinned=False,
        skill_eligible=True,
        created_at="2026-03-01T00:00:00",
    )
    list_resp = CapsuleListResponse(capsules=[capsule], total=1)
    assert list_resp.total == 1
    assert len(list_resp.capsules) == 1


def test_capture_request_schema():
    req = CaptureRequest(content="Some interesting text")
    assert req.content == "Some interesting text"
    assert req.url is None
    assert req.source_url is None
    assert req.images == []


def test_capture_request_with_url():
    req = CaptureRequest(url="https://example.com", source_url="https://example.com")
    assert req.url == "https://example.com"
    assert req.content == ""


def test_search_request_schema():
    req = SearchRequest(query="machine learning")
    assert req.query == "machine learning"
    assert req.limit == 10
    assert req.category is None
    assert req.domain is None
    assert req.difficulty is None
    assert req.author is None
    assert req.pack is None


def test_search_request_with_filters():
    req = SearchRequest(
        query="deep learning",
        limit=5,
        category="AI",
        domain="technology",
        difficulty="advanced",
    )
    assert req.limit == 5
    assert req.category == "AI"
    assert req.difficulty == "advanced"
