"""Multi-capability plugins

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

    op.execute(
        """
        INSERT INTO plugins (
          marketplace_slug, slug, display_name, description, version,
          created_at, updated_at, last_commit
        )
        SELECT
          marketplace_slug, slug, display_name, description, version,
          created_at, updated_at, last_commit
        FROM skills
        """
    )

    op.create_table(
        "skills_new",
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
    op.execute(
        """
        INSERT INTO skills_new (
          marketplace_slug, plugin_slug, slug, display_name, description, version,
          content, created_at, updated_at, last_commit
        )
        SELECT
          marketplace_slug, slug, slug, display_name, description, version,
          content, created_at, updated_at, last_commit
        FROM skills
        """
    )
    op.drop_table("skills")
    op.rename_table("skills_new", "skills")

    _create_component_tables()


def downgrade() -> None:
    op.drop_table("plugin_settings")
    op.drop_table("plugin_monitors")
    op.drop_table("plugin_commands")
    op.drop_table("plugin_mcp_servers")
    op.drop_table("plugin_agents")
    op.drop_table("plugin_hooks")

    op.create_table(
        "skills_old",
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
    op.execute(
        """
        INSERT INTO skills_old (
          marketplace_slug, slug, display_name, description, version,
          content, created_at, updated_at, last_commit
        )
        SELECT
          marketplace_slug, slug, display_name, description, version,
          content, created_at, updated_at, last_commit
        FROM skills
        WHERE plugin_slug = slug
        """
    )
    op.drop_table("skills")
    op.rename_table("skills_old", "skills")
    op.drop_table("plugins")


def _create_component_tables() -> None:
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
