"""make_password_nullable_add_oauth_provider

Revision ID: 001
Revises:
Create Date: 2026-03-01
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(200), nullable=True)
    op.add_column("users", sa.Column("oauth_provider", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "oauth_provider")
    op.alter_column("users", "password_hash", existing_type=sa.String(200), nullable=False)
