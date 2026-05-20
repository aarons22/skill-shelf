"""Add setup state and local accounts

Revision ID: 0006
Revises: 0003
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("owner_name", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("owner_email", sa.Text(), nullable=True))
    op.add_column("organizations", sa.Column("bootstrap_completed_at", sa.Integer(), nullable=True))
    op.add_column("auth_providers", sa.Column("allowlist_json", sa.Text(), nullable=True))
    op.create_table(
        "local_account_credentials",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("must_change_password", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_password_change", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("local_account_credentials")
    op.drop_column("auth_providers", "allowlist_json")
    op.drop_column("organizations", "bootstrap_completed_at")
    op.drop_column("organizations", "owner_email")
    op.drop_column("organizations", "owner_name")
