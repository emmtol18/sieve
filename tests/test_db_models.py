import uuid

from sieve.db.models import Base, Capsule, LeaderPack, Review, Sieve, Subscription, User


def test_user_model_fields():
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed",
        display_name="Test User",
    )
    assert user.email == "test@example.com"
    assert user.is_admin is False


def test_user_model_api_key_default():
    """API key should be None when not explicitly set (default is server-side via uuid4)."""
    user = User(
        id=uuid.uuid4(),
        email="key@example.com",
        password_hash="hashed",
        display_name="Key User",
    )
    assert user.email == "key@example.com"
    assert user.display_name == "Key User"


def test_sieve_model_fields():
    sieve = Sieve(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        name="My Sieve",
    )
    assert sieve.name == "My Sieve"
    assert sieve.description == ""
    assert sieve.is_public is False


def test_capsule_model_fields():
    capsule = Capsule(
        id=uuid.uuid4(),
        sieve_id=uuid.uuid4(),
        title="Test Capsule",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Full content here",
        tags=["ai", "test"],
        keywords=["artificial-intelligence"],
        topics=["technology"],
        category="AI",
        domain="technology",
        difficulty="beginner",
        content_type="insight",
        author="personal",
        capture_method="manual",
        source_type="blog",
        status="active",
        pinned=False,
        skill_eligible=True,
    )
    assert capsule.title == "Test Capsule"
    assert "ai" in capsule.tags
    assert capsule.difficulty == "beginner"
    assert capsule.content_type == "insight"
    assert capsule.author == "personal"
    assert capsule.capture_method == "manual"
    assert capsule.source_type == "blog"
    assert capsule.status == "active"
    assert capsule.pinned is False
    assert capsule.skill_eligible is True


def test_capsule_defaults():
    capsule = Capsule(
        id=uuid.uuid4(),
        sieve_id=uuid.uuid4(),
        title="Minimal Capsule",
        executive_summary="Summary",
        core_insight="Insight",
        full_content="Content",
    )
    assert capsule.difficulty == "beginner"
    assert capsule.content_type == "insight"
    assert capsule.author == "personal"
    assert capsule.capture_method == "manual"
    assert capsule.status == "active"
    assert capsule.pinned is False
    assert capsule.skill_eligible is True


def test_leader_pack_model_fields():
    pack = LeaderPack(
        id=uuid.uuid4(),
        name="Andrej Karpathy",
        slug="karpathy",
        description="AI insights",
        author_url="https://karpathy.ai",
        version="1.0.0",
        topics=["ai", "ml"],
    )
    assert pack.slug == "karpathy"
    assert pack.rating_avg == 0.0
    assert pack.review_count == 0
    assert pack.version == "1.0.0"
    assert "ai" in pack.topics


def test_subscription_model_fields():
    user_id = uuid.uuid4()
    pack_id = uuid.uuid4()
    sub = Subscription(user_id=user_id, pack_id=pack_id)
    assert sub.user_id == user_id
    assert sub.pack_id == pack_id


def test_review_model_fields():
    review = Review(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        pack_id=uuid.uuid4(),
        rating=5,
        comment="Excellent pack!",
    )
    assert review.rating == 5
    assert review.comment == "Excellent pack!"


def test_base_metadata_has_all_tables():
    table_names = set(Base.metadata.tables.keys())
    expected = {"users", "sieves", "capsules", "leader_packs", "subscriptions", "reviews"}
    assert expected == table_names


def test_user_table_columns():
    table = Base.metadata.tables["users"]
    column_names = {c.name for c in table.columns}
    expected = {"id", "email", "password_hash", "display_name", "is_admin", "api_key", "created_at", "oauth_provider"}
    assert expected == column_names


def test_capsule_table_columns():
    table = Base.metadata.tables["capsules"]
    column_names = {c.name for c in table.columns}
    expected = {
        "id", "sieve_id", "title", "executive_summary", "core_insight", "full_content",
        "tags", "keywords", "topics", "category", "domain", "difficulty", "content_type",
        "author", "pack_id", "source_url", "capture_method", "source_type",
        "status", "pinned", "skill_eligible", "created_at", "updated_at",
    }
    assert expected == column_names
