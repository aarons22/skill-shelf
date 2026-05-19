from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Integer, MetaData, PrimaryKeyConstraint, Table, Text

metadata = MetaData()

marketplaces = Table(
    "marketplaces",
    metadata,
    Column("slug", Text, primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("owner_name", Text, nullable=False),
    Column("owner_email", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
)

skills = Table(
    "skills",
    metadata,
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("version", Text, nullable=False, default="1.0.0"),
    Column("content", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    Column("last_commit", Text, nullable=True),
    PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)

plugins = Table(
    "plugins",
    metadata,
    Column("marketplace_slug", Text, ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("version", Text, nullable=False, default="1.0.0"),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    Column("last_commit", Text, nullable=True),
    PrimaryKeyConstraint("marketplace_slug", "slug"),
)

plugin_hooks = Table(
    "plugin_hooks",
    metadata,
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("event", Text, nullable=False),
    Column("matcher", Text, nullable=False),
    Column("handler_json", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)

plugin_agents = Table(
    "plugin_agents",
    metadata,
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("config_json", Text, nullable=False),
    Column("prompt", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)

plugin_mcp_servers = Table(
    "plugin_mcp_servers",
    metadata,
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("config_json", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)

plugin_commands = Table(
    "plugin_commands",
    metadata,
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("content", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)

plugin_monitors = Table(
    "plugin_monitors",
    metadata,
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("command", Text, nullable=False),
    Column("description", Text, nullable=False),
    Column("when", Text, nullable=True),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    PrimaryKeyConstraint("marketplace_slug", "plugin_slug", "slug"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)

plugin_settings = Table(
    "plugin_settings",
    metadata,
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("settings_json", Text, nullable=False),
    Column("updated_at", Integer, nullable=False),
    PrimaryKeyConstraint("marketplace_slug", "plugin_slug"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)
