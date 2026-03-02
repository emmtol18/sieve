"""add_skills_tables

Revision ID: 003
Revises: 002
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "sieve_id",
            UUID(as_uuid=True),
            sa.ForeignKey("sieves.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(50), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skills_sieve_id", "skills", ["sieve_id"])
    op.create_index("ix_skills_name", "skills", ["name"])

    op.create_table(
        "skill_capsules",
        sa.Column(
            "skill_id",
            UUID(as_uuid=True),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "capsule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("capsules.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(50), server_default="primary", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("skill_capsules")
    op.drop_index("ix_skills_name", table_name="skills")
    op.drop_index("ix_skills_sieve_id", table_name="skills")
    op.drop_table("skills")
