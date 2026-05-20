"""Add organizations and auth providers

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
    )
    now = int(__import__("time").time())
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, slug, display_name, created_at, updated_at) "
            "VALUES (1, 'default', 'Default Organization', :now, :now)"
        ).bindparams(now=now)
    )

    for table_name in (
        "marketplaces",
        "workspace_settings",
        "users",
        "groups",
        "user_groups",
        "workspace_role_grants",
        "marketplace_role_grants",
        "plugin_role_grants",
        "access_tokens",
        "audit_events",
    ):
        op.add_column(
            table_name,
            sa.Column("organization_id", sa.Integer(), nullable=False, server_default="1"),
        )

    op.execute(
        "UPDATE workspace_role_grants SET role = 'organization_admin' WHERE role = 'workspace_admin'"
    )

    op.create_table(
        "auth_providers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, server_default="1"),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("client_id", sa.Text(), nullable=False),
        sa.Column("client_secret_env_var", sa.Text(), nullable=False),
        sa.Column("issuer_url", sa.Text(), nullable=True),
        sa.Column("authorization_url", sa.Text(), nullable=True),
        sa.Column("token_url", sa.Text(), nullable=True),
        sa.Column("userinfo_url", sa.Text(), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("group_claim", sa.Text(), nullable=True),
        sa.Column("allowed_orgs", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.UniqueConstraint("organization_id", "slug"),
    )


def downgrade() -> None:
    op.drop_table("auth_providers")
    op.execute(
        "UPDATE workspace_role_grants SET role = 'workspace_admin' WHERE role = 'organization_admin'"
    )
    for table_name in (
        "audit_events",
        "access_tokens",
        "plugin_role_grants",
        "marketplace_role_grants",
        "workspace_role_grants",
        "user_groups",
        "groups",
        "users",
        "workspace_settings",
        "marketplaces",
    ):
        op.drop_column(table_name, "organization_id")
    op.drop_table("organizations")
