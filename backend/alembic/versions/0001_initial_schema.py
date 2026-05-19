"""Initial SkillShelf schema

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
        "plugins",
        sa.Column("marketplace_slug", sa.Text, sa.ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False, server_default="1.0.0"),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.Column("last_commit", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("marketplace_slug", "slug"),
    )
    op.create_table(
        "skills",
        sa.Column("marketplace_slug", sa.Text, nullable=False),
        sa.Column("plugin_slug", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("version", sa.Text, nullable=False, server_default="1.0.0"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.Column("last_commit", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
        sa.ForeignKeyConstraint(
            ["marketplace_slug", "plugin_slug"],
            ["plugins.marketplace_slug", "plugins.slug"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "plugin_hooks",
        sa.Column("marketplace_slug", sa.Text, nullable=False),
        sa.Column("plugin_slug", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("event", sa.Text, nullable=False),
        sa.Column("matcher", sa.Text, nullable=False),
        sa.Column("handler_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
        sa.ForeignKeyConstraint(["marketplace_slug", "plugin_slug"], ["plugins.marketplace_slug", "plugins.slug"], ondelete="CASCADE"),
    )
    op.create_table(
        "plugin_agents",
        sa.Column("marketplace_slug", sa.Text, nullable=False),
        sa.Column("plugin_slug", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("config_json", sa.Text, nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
        sa.ForeignKeyConstraint(["marketplace_slug", "plugin_slug"], ["plugins.marketplace_slug", "plugins.slug"], ondelete="CASCADE"),
    )
    op.create_table(
        "plugin_mcp_servers",
        sa.Column("marketplace_slug", sa.Text, nullable=False),
        sa.Column("plugin_slug", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("config_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
        sa.ForeignKeyConstraint(["marketplace_slug", "plugin_slug"], ["plugins.marketplace_slug", "plugins.slug"], ondelete="CASCADE"),
    )
    op.create_table(
        "plugin_commands",
        sa.Column("marketplace_slug", sa.Text, nullable=False),
        sa.Column("plugin_slug", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
        sa.ForeignKeyConstraint(["marketplace_slug", "plugin_slug"], ["plugins.marketplace_slug", "plugins.slug"], ondelete="CASCADE"),
    )
    op.create_table(
        "plugin_monitors",
        sa.Column("marketplace_slug", sa.Text, nullable=False),
        sa.Column("plugin_slug", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("command", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("when", sa.Text, nullable=True),
        sa.Column("created_at", sa.Integer, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
        sa.ForeignKeyConstraint(["marketplace_slug", "plugin_slug"], ["plugins.marketplace_slug", "plugins.slug"], ondelete="CASCADE"),
    )
    op.create_table(
        "plugin_settings",
        sa.Column("marketplace_slug", sa.Text, nullable=False),
        sa.Column("plugin_slug", sa.Text, nullable=False),
        sa.Column("settings_json", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("marketplace_slug", "plugin_slug"),
        sa.ForeignKeyConstraint(["marketplace_slug", "plugin_slug"], ["plugins.marketplace_slug", "plugins.slug"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("plugin_settings")
    op.drop_table("plugin_monitors")
    op.drop_table("plugin_commands")
    op.drop_table("plugin_mcp_servers")
    op.drop_table("plugin_agents")
    op.drop_table("plugin_hooks")
    op.drop_table("skills")
    op.drop_table("plugins")
    op.drop_table("marketplaces")
