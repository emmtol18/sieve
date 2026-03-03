"""evolve_leader_pack_to_leader

Revision ID: 004
Revises: 003
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Add new profile columns to leader_packs (before rename) ---
    op.add_column("leader_packs", sa.Column("avatar_url", sa.String(2000), nullable=True))
    op.add_column("leader_packs", sa.Column("bio", sa.String(500), nullable=True))
    op.add_column("leader_packs", sa.Column("expertise_domain", sa.String(100), nullable=True))
    op.add_column("leader_packs", sa.Column("twitter_url", sa.String(500), nullable=True))
    op.add_column("leader_packs", sa.Column("linkedin_url", sa.String(500), nullable=True))
    op.add_column(
        "leader_packs",
        sa.Column("is_featured", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "leader_packs",
        sa.Column("capsule_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )

    # --- 2. Drop FK constraints that reference leader_packs ---
    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")

    # --- 3. Rename the table ---
    op.rename_table("leader_packs", "leaders")

    # --- 4. Re-create FK constraints pointing to the renamed table ---
    op.create_foreign_key(
        "capsules_pack_id_fkey",
        "capsules",
        "leaders",
        ["pack_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "subscriptions_pack_id_fkey",
        "subscriptions",
        "leaders",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "reviews_pack_id_fkey",
        "reviews",
        "leaders",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # --- 1. Drop FK constraints that reference leaders ---
    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")

    # --- 2. Rename the table back ---
    op.rename_table("leaders", "leader_packs")

    # --- 3. Re-create FK constraints pointing to the original table ---
    op.create_foreign_key(
        "capsules_pack_id_fkey",
        "capsules",
        "leader_packs",
        ["pack_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "subscriptions_pack_id_fkey",
        "subscriptions",
        "leader_packs",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "reviews_pack_id_fkey",
        "reviews",
        "leader_packs",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- 4. Drop the new columns ---
    op.drop_column("leader_packs", "capsule_count")
    op.drop_column("leader_packs", "is_featured")
    op.drop_column("leader_packs", "linkedin_url")
    op.drop_column("leader_packs", "twitter_url")
    op.drop_column("leader_packs", "expertise_domain")
    op.drop_column("leader_packs", "bio")
    op.drop_column("leader_packs", "avatar_url")
