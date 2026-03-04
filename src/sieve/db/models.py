import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all models.

    Uses an init event listener to apply column-level defaults at Python
    construction time, not just at INSERT time. This allows
    ``User(email="x").is_admin`` to return ``False`` instead of ``None``
    before the instance is persisted.
    """

    pass


from sqlalchemy import event  # noqa: E402


@event.listens_for(Base, "init", propagate=True)
def _apply_column_defaults(target: Base, args: tuple, kwargs: dict) -> None:
    """Inject column defaults into kwargs so the ORM __init__ applies them."""
    for column in target.__table__.columns:
        attr_name = column.key
        if attr_name not in kwargs and column.default is not None:
            default = column.default
            if default.is_callable:
                kwargs[attr_name] = default.arg(None)  # type: ignore[arg-type]
            elif default.is_scalar:
                kwargs[attr_name] = default.arg


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    oauth_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    api_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sieve: Mapped["Sieve"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Sieve(Base):
    __tablename__ = "sieves"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), default="")
    bio: Mapped[str] = mapped_column(String(500), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="sieve")
    capsules: Mapped[list["Capsule"]] = relationship(
        back_populates="sieve", cascade="all, delete-orphan"
    )
    followers: Mapped[list["Follow"]] = relationship(
        foreign_keys="Follow.followed_sieve_id",
        cascade="all, delete-orphan",
    )
    following: Mapped[list["Follow"]] = relationship(
        foreign_keys="Follow.follower_sieve_id",
        cascade="all, delete-orphan",
    )


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("follower_sieve_id", "followed_sieve_id", name="uq_follow_pair"),
        CheckConstraint(
            "follower_sieve_id != followed_sieve_id",
            name="ck_follow_no_self_follow",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    follower_sieve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sieves.id", ondelete="CASCADE"),
        nullable=False,
    )
    followed_sieve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sieves.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Capsule(Base):
    __tablename__ = "capsules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sieve_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sieves.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Content fields
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    executive_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    core_insight: Mapped[str] = mapped_column(String(2000), nullable=False)
    full_content: Mapped[str] = mapped_column(Text, nullable=False)

    # Discovery metadata
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    category: Mapped[str] = mapped_column(String(200), nullable=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(50), default="beginner")
    content_type: Mapped[str] = mapped_column(String(50), default="insight")

    # Provenance
    author: Mapped[str] = mapped_column(String(200), default="personal")
    pack_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creators.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    capture_method: Mapped[str] = mapped_column(String(50), default="manual")
    source_type: Mapped[str] = mapped_column(String(50), nullable=True)

    # System
    status: Mapped[str] = mapped_column(String(50), default="active")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    skill_eligible: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relationships
    sieve: Mapped["Sieve"] = relationship(back_populates="capsules")
    pack: Mapped["Creator | None"] = relationship(back_populates="capsules")


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sieve_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sieves.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sieve: Mapped["Sieve"] = relationship()
    capsule_links: Mapped[list["SkillCapsule"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )


class SkillCapsule(Base):
    __tablename__ = "skill_capsules"

    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    capsule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String(50), default="primary")

    skill: Mapped["Skill"] = relationship(back_populates="capsule_links")
    capsule: Mapped["Capsule"] = relationship()


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author_url: Mapped[str] = mapped_column(String(2000), nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0")
    topics: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # New profile fields
    avatar_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expertise_domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    twitter_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    capsule_count: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    capsules: Mapped[list["Capsule"]] = relationship(back_populates="pack")
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "pack_id", name="uq_subscription_user_pack"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creators.id", ondelete="CASCADE"),
        primary_key=True,
    )
    subscribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped["User"] = relationship()
    pack: Mapped["Creator"] = relationship(back_populates="subscriptions")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("user_id", "pack_id", name="uq_review_user_pack"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    pack_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("creators.id", ondelete="CASCADE"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped["User"] = relationship()
    pack: Mapped["Creator"] = relationship(back_populates="reviews")
