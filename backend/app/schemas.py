from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class MarketplaceCreate(BaseModel):
    displayName: str


class MarketplaceUpdate(BaseModel):
    displayName: Optional[str] = None
    visibility: Optional[Literal["workspace", "restricted"]] = None


class MarketplaceOut(BaseModel):
    slug: str
    displayName: str
    ownerName: str
    ownerEmail: str
    visibility: Literal["workspace", "restricted"] = "workspace"
    createdAt: int
    updatedAt: int
    skillCount: Optional[int] = None
    pluginCount: Optional[int] = None


class PluginCreate(BaseModel):
    displayName: str
    description: str


class PluginUpdate(BaseModel):
    displayName: Optional[str] = None
    description: Optional[str] = None


class PluginOut(BaseModel):
    marketplaceSlug: str
    slug: str
    displayName: str
    description: str
    version: str
    createdAt: int
    updatedAt: int
    lastCommit: Optional[str] = None
    skillCount: int = 0
    hookCount: int = 0
    agentCount: int = 0
    mcpServerCount: int = 0
    commandCount: int = 0
    monitorCount: int = 0
    hasSettings: bool = False


class SkillCreate(BaseModel):
    displayName: str
    description: str
    content: str


class SkillUpdate(BaseModel):
    displayName: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class SkillOut(BaseModel):
    marketplaceSlug: str
    pluginSlug: Optional[str] = None
    slug: str
    displayName: str
    description: str
    version: str
    content: Optional[str] = None
    createdAt: int
    updatedAt: int
    lastCommit: Optional[str] = None


class HookHandler(BaseModel):
    type: Literal["command", "http", "mcp_tool", "prompt", "agent"]
    command: Optional[str] = None
    args: Optional[list[str]] = None
    timeout: Optional[int] = None
    url: Optional[str] = None
    prompt: Optional[str] = None
    name: Optional[str] = None
    server: Optional[str] = None
    tool: Optional[str] = None
    input: Optional[dict[str, Any]] = None


class HookCreate(BaseModel):
    displayName: str
    event: str
    matcher: str = ""
    handler: HookHandler
    unsafeConfirmed: bool = False

    @field_validator("unsafeConfirmed")
    @classmethod
    def unsafe_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Executable plugin components require explicit confirmation")
        return value


class HookUpdate(BaseModel):
    displayName: Optional[str] = None
    event: Optional[str] = None
    matcher: Optional[str] = None
    handler: Optional[HookHandler] = None
    unsafeConfirmed: bool = False

    @field_validator("unsafeConfirmed")
    @classmethod
    def update_unsafe_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Executable plugin components require explicit confirmation")
        return value


class HookOut(BaseModel):
    marketplaceSlug: str
    pluginSlug: str
    slug: str
    displayName: str
    event: str
    matcher: str
    handler: dict[str, Any]
    createdAt: int
    updatedAt: int


class AgentCreate(BaseModel):
    displayName: str
    description: str
    prompt: str
    config: dict[str, Any] = Field(default_factory=dict)


class AgentUpdate(BaseModel):
    displayName: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    config: Optional[dict[str, Any]] = None


class AgentOut(BaseModel):
    marketplaceSlug: str
    pluginSlug: str
    slug: str
    displayName: str
    description: str
    prompt: str
    config: dict[str, Any]
    createdAt: int
    updatedAt: int


class McpServerCreate(BaseModel):
    displayName: str
    config: dict[str, Any]
    unsafeConfirmed: bool = False

    @field_validator("unsafeConfirmed")
    @classmethod
    def mcp_unsafe_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Executable plugin components require explicit confirmation")
        return value


class McpServerUpdate(BaseModel):
    displayName: Optional[str] = None
    config: Optional[dict[str, Any]] = None
    unsafeConfirmed: bool = False

    @field_validator("unsafeConfirmed")
    @classmethod
    def update_mcp_unsafe_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Executable plugin components require explicit confirmation")
        return value


class McpServerOut(BaseModel):
    marketplaceSlug: str
    pluginSlug: str
    slug: str
    displayName: str
    config: dict[str, Any]
    createdAt: int
    updatedAt: int


class CommandCreate(BaseModel):
    displayName: str
    description: str
    content: str


class CommandUpdate(BaseModel):
    displayName: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class CommandOut(BaseModel):
    marketplaceSlug: str
    pluginSlug: str
    slug: str
    displayName: str
    description: str
    content: str
    createdAt: int
    updatedAt: int


class MonitorCreate(BaseModel):
    displayName: str
    command: str
    description: str
    when: Optional[str] = None
    unsafeConfirmed: bool = False

    @field_validator("unsafeConfirmed")
    @classmethod
    def monitor_unsafe_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Executable plugin components require explicit confirmation")
        return value


class MonitorUpdate(BaseModel):
    displayName: Optional[str] = None
    command: Optional[str] = None
    description: Optional[str] = None
    when: Optional[str] = None
    unsafeConfirmed: bool = False

    @field_validator("unsafeConfirmed")
    @classmethod
    def update_monitor_unsafe_must_be_confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Executable plugin components require explicit confirmation")
        return value


class MonitorOut(BaseModel):
    marketplaceSlug: str
    pluginSlug: str
    slug: str
    displayName: str
    command: str
    description: str
    when: Optional[str] = None
    createdAt: int
    updatedAt: int


class PluginSettingsIn(BaseModel):
    settings: dict[str, Any]


class PluginSettingsOut(BaseModel):
    marketplaceSlug: str
    pluginSlug: str
    settings: dict[str, Any]
    updatedAt: int


class CurrentUserOut(BaseModel):
    authenticated: bool
    id: Optional[int] = None
    email: Optional[str] = None
    displayName: Optional[str] = None
    user: Optional[dict[str, Any]] = None
    workspaceAdmin: bool = False
    organizationAdmin: bool = False
    marketplaceAdminSlugs: list[str] = Field(default_factory=list)
    marketplaceMaintainerSlugs: list[str] = Field(default_factory=list)
    marketplaceContributorSlugs: list[str] = Field(default_factory=list)
    provider: Optional[str] = None
    loginConfigured: bool = False
    bootstrapRequired: bool = False
    bootstrapCompleted: bool = True
    mustChangePassword: bool = False
    accessMode: Literal["public", "authenticated", "restricted"] = "public"
    marketplaceCreation: Literal["authenticated", "organization_admin"] = "authenticated"
    publicBaseUrl: str = "http://localhost:3000"


class WorkspaceSettingsOut(BaseModel):
    accessMode: Literal["public", "authenticated", "restricted"]
    marketplaceCreation: Literal["authenticated", "organization_admin"]


class WorkspaceSettingsUpdate(BaseModel):
    accessMode: Optional[Literal["public", "authenticated", "restricted"]] = None
    marketplaceCreation: Optional[Literal["authenticated", "organization_admin"]] = None


class PrincipalGrantIn(BaseModel):
    principalType: Literal["user", "group"]
    principalId: int
    role: Literal["marketplace_admin", "marketplace_maintainer", "marketplace_contributor", "viewer"]


class MarketplaceGrantOut(BaseModel):
    marketplaceSlug: str
    principalType: Literal["user", "group"]
    principalId: int
    role: str
    createdAt: int


class MarketplaceUserOut(BaseModel):
    id: int
    email: str
    displayName: str
    provider: str
    marketplaceRole: Literal["none", "viewer", "marketplace_contributor", "marketplace_maintainer", "marketplace_admin"] = "none"
    isOwner: bool = False


class MarketplaceUserRoleUpdate(BaseModel):
    marketplaceRole: Literal["none", "viewer", "marketplace_contributor", "marketplace_maintainer", "marketplace_admin"]


class AccessTokenCreate(BaseModel):
    name: str
    marketplaceSlug: Optional[str] = None
    expiresAt: Optional[int] = None


class AccessTokenCreatedOut(BaseModel):
    id: int
    name: str
    token: str
    scope: str
    marketplaceSlug: Optional[str] = None
    expiresAt: Optional[int] = None
    createdAt: int


class AccessTokenOut(BaseModel):
    id: int
    name: str
    scope: str
    marketplaceSlug: Optional[str] = None
    expiresAt: Optional[int] = None
    revokedAt: Optional[int] = None
    createdAt: int


class AuthProviderIn(BaseModel):
    slug: str
    displayName: str
    providerType: Literal["local", "github", "oidc", "trusted_header", "trusted_headers"]
    enabled: bool = True
    clientId: str = ""
    clientSecret: str = ""
    issuerUrl: Optional[str] = None
    authorizationUrl: Optional[str] = None
    tokenUrl: Optional[str] = None
    userinfoUrl: Optional[str] = None
    scopes: str = "openid email profile"
    groupClaim: Optional[str] = None
    allowedOrgs: Optional[str] = None
    allowlist: Optional[dict[str, Any]] = None


class AuthProviderUpdate(BaseModel):
    displayName: Optional[str] = None
    enabled: Optional[bool] = None
    clientId: Optional[str] = None
    clientSecret: Optional[str] = None
    issuerUrl: Optional[str] = None
    authorizationUrl: Optional[str] = None
    tokenUrl: Optional[str] = None
    userinfoUrl: Optional[str] = None
    scopes: Optional[str] = None
    groupClaim: Optional[str] = None
    allowedOrgs: Optional[str] = None
    allowlist: Optional[dict[str, Any]] = None


class AuthProviderOut(BaseModel):
    id: int
    slug: str
    displayName: str
    providerType: Literal["local", "github", "oidc", "trusted_header", "trusted_headers"]
    enabled: bool
    clientId: str
    secretConfigured: bool
    issuerUrl: Optional[str] = None
    authorizationUrl: Optional[str] = None
    tokenUrl: Optional[str] = None
    userinfoUrl: Optional[str] = None
    scopes: str
    groupClaim: Optional[str] = None
    allowedOrgs: Optional[str] = None
    allowlist: Optional[dict[str, Any]] = None
    loginUrl: str
    callbackUrl: Optional[str] = None
    createdAt: int
    updatedAt: int


class SetupStatusOut(BaseModel):
    required: bool
    completed: bool


class LocalSetupAdmin(BaseModel):
    email: str
    displayName: str
    password: str


class SetupProviderIn(BaseModel):
    provider: Literal["local", "github", "oidc", "trusted_header", "trusted_headers"] = "local"
    admin: Optional[LocalSetupAdmin] = None
    slug: str = "local"
    displayName: str = "Local Accounts"
    clientId: str = ""
    clientSecret: str = ""
    issuerUrl: Optional[str] = None
    authorizationUrl: Optional[str] = None
    tokenUrl: Optional[str] = None
    userinfoUrl: Optional[str] = None
    scopes: str = "openid email profile"
    groupClaim: Optional[str] = None
    allowlist: Optional[dict[str, Any]] = None


class OrganizationSetupIn(BaseModel):
    displayName: str
    ownerName: Optional[str] = None
    ownerEmail: Optional[str] = None
    accessMode: Literal["public", "authenticated", "restricted"] = "public"
    marketplaceCreation: Literal["authenticated", "organization_admin"] = "authenticated"
    provider: SetupProviderIn


class LoginLocalIn(BaseModel):
    email: str
    password: str


class ChangePasswordIn(BaseModel):
    currentPassword: str = Field(alias="current_password")
    newPassword: str = Field(alias="new_password")

    model_config = {"populate_by_name": True}


class PublicAuthProviderOut(BaseModel):
    slug: str
    displayName: str
    providerType: str
    kind: Literal["credentials", "redirect", "trusted_header"]
    loginUrl: str


class OrganizationUserOut(BaseModel):
    id: int
    email: str
    displayName: str
    provider: str
    organizationRole: Literal["organization_admin", "viewer"] = "viewer"
    disabledAt: Optional[int] = None
    mustChangePassword: bool = False
    createdAt: int
    updatedAt: int


class OrganizationUserCreate(BaseModel):
    email: str
    displayName: str


class OrganizationUserRoleUpdate(BaseModel):
    organizationRole: Literal["organization_admin", "viewer"]


class OrganizationUserCreatedOut(OrganizationUserOut):
    temporaryPassword: str
