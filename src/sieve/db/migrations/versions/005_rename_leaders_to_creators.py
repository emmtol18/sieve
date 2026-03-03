"""rename_leaders_to_creators_and_nullable_sieve_id

Revision ID: 005
Revises: 004
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop FK constraints referencing leaders
    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")

    # 2. Rename table
    op.rename_table("leaders", "creators")

    # 3. Re-create FK constraints pointing to creators
    op.create_foreign_key(
        "capsules_pack_id_fkey",
        "capsules",
        "creators",
        ["pack_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "subscriptions_pack_id_fkey",
        "subscriptions",
        "creators",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "reviews_pack_id_fkey",
        "reviews",
        "creators",
        ["pack_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 4. Make capsules.sieve_id nullable (creator pack capsules have no personal sieve)
    op.alter_column("capsules", "sieve_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    op.alter_column("capsules", "sieve_id", existing_type=sa.UUID(), nullable=False)

    op.drop_constraint("capsules_pack_id_fkey", "capsules", type_="foreignkey")
    op.drop_constraint("subscriptions_pack_id_fkey", "subscriptions", type_="foreignkey")
    op.drop_constraint("reviews_pack_id_fkey", "reviews", type_="foreignkey")

    op.rename_table("creators", "leaders")

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
