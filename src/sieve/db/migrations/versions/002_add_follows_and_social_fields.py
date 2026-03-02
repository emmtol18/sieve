"""add_follows_and_social_fields

Revision ID: 002
Revises: 001
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add username column to users (nullable initially for backfill)
    op.add_column("users", sa.Column("username", sa.String(50), nullable=True))
    op.create_unique_constraint("uq_users_username", "users", ["username"])

    # Add social fields to sieves
    op.add_column("sieves", sa.Column("bio", sa.String(500), server_default="", nullable=False))
    op.add_column("sieves", sa.Column("avatar_url", sa.String(2000), nullable=True))

    # Create follows table
    op.create_table(
        "follows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "follower_sieve_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sieves.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "followed_sieve_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sieves.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("follower_sieve_id", "followed_sieve_id", name="uq_follow_pair"),
        sa.CheckConstraint(
            "follower_sieve_id != followed_sieve_id",
            name="ck_follow_no_self_follow",
        ),
    )


def downgrade() -> None:
    op.drop_table("follows")
    op.drop_column("sieves", "avatar_url")
    op.drop_column("sieves", "bio")
    op.drop_constraint("uq_users_username", "users", type_="unique")
    op.drop_column("users", "username")
