"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "marketplaces",
        sa.Column("slug", sa.Text, primary_key=True),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("owner_name", sa.Text, nullable=False),
        sa.Column("owner_email", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
    )
    op.create_table(
        "skills",
        sa.Column("marketplace_slug", sa.Text, sa.ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False, server_default="1.0.0"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.Column("last_commit", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("marketplace_slug", "slug"),
    )


def downgrade() -> None:
    op.drop_table("skills")
    op.drop_table("marketplaces")
