from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint, Integer, MetaData, PrimaryKeyConstraint, Table, Text, UniqueConstraint

metadata = MetaData()

organizations = Table(
    "organizations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("slug", Text, nullable=False, unique=True),
    Column("display_name", Text, nullable=False),
    Column("owner_name", Text, nullable=True),
    Column("owner_email", Text, nullable=True),
    Column("bootstrap_completed_at", Integer, nullable=True),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
)

marketplaces = Table(
    "marketplaces",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("slug", Text, primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("owner_name", Text, nullable=False),
    Column("owner_email", Text, nullable=False),
    Column("visibility", Text, nullable=False, default="workspace"),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
)

organization_settings = Table(
    "organization_settings",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("access_mode", Text, nullable=False, default="public"),
    Column("marketplace_creation", Text, nullable=False, default="authenticated"),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
)

users = Table(
    "users",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", Text, nullable=False),
    Column("provider_subject", Text, nullable=False),
    Column("email", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("disabled_at", Integer, nullable=True),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    UniqueConstraint("provider", "provider_subject"),
    UniqueConstraint("email"),
)

groups = Table(
    "groups",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("provider", Text, nullable=False),
    Column("provider_key", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    UniqueConstraint("provider", "provider_key"),
)

user_groups = Table(
    "user_groups",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("group_id", Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", Integer, nullable=False),
    PrimaryKeyConstraint("organization_id", "user_id", "group_id"),
)

organization_role_grants = Table(
    "organization_role_grants",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("principal_type", Text, nullable=False),
    Column("principal_id", Integer, nullable=False),
    Column("role", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    PrimaryKeyConstraint("organization_id", "principal_type", "principal_id", "role"),
)

marketplace_role_grants = Table(
    "marketplace_role_grants",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("marketplace_slug", Text, ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=False),
    Column("principal_type", Text, nullable=False),
    Column("principal_id", Integer, nullable=False),
    Column("role", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    PrimaryKeyConstraint("organization_id", "marketplace_slug", "principal_type", "principal_id", "role"),
)

plugin_role_grants = Table(
    "plugin_role_grants",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("marketplace_slug", Text, nullable=False),
    Column("plugin_slug", Text, nullable=False),
    Column("principal_type", Text, nullable=False),
    Column("principal_id", Integer, nullable=False),
    Column("role", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
    PrimaryKeyConstraint("organization_id", "marketplace_slug", "plugin_slug", "principal_type", "principal_id", "role"),
    ForeignKeyConstraint(
        ["marketplace_slug", "plugin_slug"],
        ["plugins.marketplace_slug", "plugins.slug"],
        ondelete="CASCADE",
    ),
)

access_tokens = Table(
    "access_tokens",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", Text, nullable=False),
    Column("token_hash", Text, nullable=False, unique=True),
    Column("scope", Text, nullable=False),
    Column("marketplace_slug", Text, ForeignKey("marketplaces.slug", ondelete="CASCADE"), nullable=True),
    Column("created_by_user_id", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("created_at", Integer, nullable=False),
    Column("expires_at", Integer, nullable=True),
    Column("revoked_at", Integer, nullable=True),
)

audit_events = Table(
    "audit_events",
    metadata,
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("actor_user_id", Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    Column("action", Text, nullable=False),
    Column("target_type", Text, nullable=False),
    Column("target_id", Text, nullable=False),
    Column("metadata_json", Text, nullable=False),
    Column("created_at", Integer, nullable=False),
)

auth_providers = Table(
    "auth_providers",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("organization_id", Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, default=1),
    Column("slug", Text, nullable=False),
    Column("display_name", Text, nullable=False),
    Column("provider_type", Text, nullable=False),
    Column("enabled", Integer, nullable=False, default=1),
    Column("client_id", Text, nullable=False),
    Column("client_secret_env_var", Text, nullable=False),
    Column("issuer_url", Text, nullable=True),
    Column("authorization_url", Text, nullable=True),
    Column("token_url", Text, nullable=True),
    Column("userinfo_url", Text, nullable=True),
    Column("scopes", Text, nullable=False),
    Column("group_claim", Text, nullable=True),
    Column("allowed_orgs", Text, nullable=True),
    Column("allowlist_json", Text, nullable=True),
    Column("created_at", Integer, nullable=False),
    Column("updated_at", Integer, nullable=False),
    UniqueConstraint("organization_id", "slug"),
)

local_account_credentials = Table(
    "local_account_credentials",
    metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("password_hash", Text, nullable=False),
    Column("must_change_password", Integer, nullable=False, default=0),
    Column("last_password_change", Integer, nullable=False),
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
