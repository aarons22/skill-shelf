from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class MarketplaceCreate(BaseModel):
    displayName: str
    ownerName: str
    ownerEmail: str


class MarketplaceUpdate(BaseModel):
    displayName: Optional[str] = None
    ownerName: Optional[str] = None
    ownerEmail: Optional[str] = None


class MarketplaceOut(BaseModel):
    slug: str
    displayName: str
    ownerName: str
    ownerEmail: str
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
