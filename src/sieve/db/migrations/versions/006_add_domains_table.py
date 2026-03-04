"""add_domains_table

Revision ID: 006
Revises: 005
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

DOMAINS = [
    ("AI/ML", "ai-ml", 0),
    ("Developer Tools", "developer-tools", 1),
    ("Search & Retrieval", "search-retrieval", 2),
    ("Startups & Indie Hacking", "startups-indie-hacking", 3),
    ("Product & Design", "product-design", 4),
    ("Engineering Leadership", "engineering-leadership", 5),
    ("Open Source", "open-source", 6),
    ("Security", "security", 7),
    ("Data & Infrastructure", "data-infrastructure", 8),
]


def upgrade() -> None:
    domains_table = op.create_table(
        "domains",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("sort_order", sa.Integer, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.bulk_insert(
        domains_table,
        [
            {"id": uuid.uuid4(), "name": name, "slug": slug, "sort_order": order}
            for name, slug, order in DOMAINS
        ],
    )


def downgrade() -> None:
    op.drop_table("domains")
