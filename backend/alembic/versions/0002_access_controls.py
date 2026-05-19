"""Add access controls and identity tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("marketplaces", sa.Column("visibility", sa.Text(), nullable=False, server_default="workspace"))

    op.create_table(
        "workspace_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("access_mode", sa.Text(), nullable=False, server_default="public"),
        sa.Column("marketplace_creation", sa.Text(), nullable=False, server_default="authenticated"),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_subject", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("disabled_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("provider", "provider_subject"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("provider", "provider_key"),
    )
    op.create_table(
        "user_groups",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "group_id"),
    )
    op.create_table(
        "workspace_role_grants",
        sa.Column("principal_type", sa.Text(), nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("principal_type", "principal_id", "role"),
    )
    op.create_table(
        "marketplace_role_grants",
        sa.Column("marketplace_slug", sa.Text(), sa.ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=False),
        sa.Column("principal_type", sa.Text(), nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "principal_type", "principal_id", "role"),
    )
    op.create_table(
        "plugin_role_grants",
        sa.Column("marketplace_slug", sa.Text(), nullable=False),
        sa.Column("plugin_slug", sa.Text(), nullable=False),
        sa.Column("principal_type", sa.Text(), nullable=False),
        sa.Column("principal_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "principal_type", "principal_id", "role"),
        sa.ForeignKeyConstraint(
            ["marketplace_slug", "plugin_slug"],
            ["plugins.marketplace_slug", "plugins.slug"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "access_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("marketplace_slug", sa.Text(), sa.ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.Integer(), nullable=True),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("access_tokens")
    op.drop_table("plugin_role_grants")
    op.drop_table("marketplace_role_grants")
    op.drop_table("workspace_role_grants")
    op.drop_table("user_groups")
    op.drop_table("groups")
    op.drop_table("users")
    op.drop_table("workspace_settings")
    op.drop_column("marketplaces", "visibility")
