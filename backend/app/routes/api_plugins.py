import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, insert, select, update

from app.db import get_connection, get_transaction
from app.lib.auth import public_read_dependencies, record_audit, require_marketplace_maintain, require_marketplace_read, require_marketplace_write
from app.lib import git_store, write_path
from app.lib.locks import marketplace_write_lock
from app.lib.slug import make_slug
from app.models import (
    marketplaces,
    plugin_agents,
    plugin_commands,
    plugin_hooks,
    plugin_mcp_servers,
    plugin_monitors,
    plugin_settings,
    plugins,
    skills,
)
from app.schemas import (
    AgentCreate,
    AgentOut,
    AgentUpdate,
    CommandCreate,
    CommandOut,
    CommandUpdate,
    HookCreate,
    HookOut,
    HookUpdate,
    McpServerCreate,
    McpServerOut,
    McpServerUpdate,
    MonitorCreate,
    MonitorOut,
    MonitorUpdate,
    PluginCreate,
    PluginOut,
    PluginSettingsIn,
    PluginSettingsOut,
    PluginUpdate,
    SkillCreate,
    SkillOut,
    SkillUpdate,
)

router = APIRouter(
    prefix="/api/marketplaces/{marketplace_slug}/plugins",
    tags=["plugins"],
    dependencies=[Depends(public_read_dependencies)],
)


def _actor(request: Request):
    return getattr(request.state, "actor", None)


def _bump_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) == 3:
        parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def _get_marketplace_or_404(conn, slug: str):
    row = conn.execute(select(marketplaces).where(marketplaces.c.slug == slug)).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    return row


def _get_plugin_or_404(conn, marketplace_slug: str, plugin_slug: str):
    row = conn.execute(
        select(plugins).where(
            plugins.c.marketplace_slug == marketplace_slug,
            plugins.c.slug == plugin_slug,
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return row


def _plugin_counts(conn, marketplace_slug: str, plugin_slug: str) -> dict[str, Any]:
    def count(table) -> int:
        return conn.execute(
            select(func.count()).where(
                table.c.marketplace_slug == marketplace_slug,
                table.c.plugin_slug == plugin_slug,
            )
        ).scalar() or 0

    has_settings = conn.execute(
        select(plugin_settings.c.plugin_slug).where(
            plugin_settings.c.marketplace_slug == marketplace_slug,
            plugin_settings.c.plugin_slug == plugin_slug,
        )
    ).one_or_none() is not None
    return {
        "skillCount": count(skills),
        "hookCount": count(plugin_hooks),
        "agentCount": count(plugin_agents),
        "mcpServerCount": count(plugin_mcp_servers),
        "commandCount": count(plugin_commands),
        "monitorCount": count(plugin_monitors),
        "hasSettings": has_settings,
    }


def _plugin_out(row, conn) -> dict[str, Any]:
    return {
        "marketplaceSlug": row["marketplace_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "description": row["description"],
        "version": row["version"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "lastCommit": row["last_commit"],
        **_plugin_counts(conn, row["marketplace_slug"], row["slug"]),
    }


def _skill_out(row, include_content: bool = True) -> dict[str, Any]:
    out = {
        "marketplaceSlug": row["marketplace_slug"],
        "pluginSlug": row["plugin_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "description": row["description"],
        "version": row["version"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "lastCommit": row["last_commit"],
    }
    if include_content:
        out["content"] = row["content"]
    return out


def _json_out(value: str) -> dict[str, Any]:
    return json.loads(value)


def _sync_plugin(
    conn,
    marketplace_slug: str,
    plugin_slug: str,
    commit_message: str,
    extra_files: dict[str, str | None] | None = None,
) -> str:
    files = write_path.build_plugin_files(marketplace_slug, plugin_slug, conn)
    if extra_files:
        files.update(extra_files)
    sha = write_path.sync_and_commit(
        marketplace_slug,
        conn,
        commit_message=commit_message,
        extra_files=files,
    )
    conn.execute(
        update(plugins).where(
            plugins.c.marketplace_slug == marketplace_slug,
            plugins.c.slug == plugin_slug,
        ).values(last_commit=sha)
    )
    return sha


@router.get("", response_model=list[PluginOut])
def list_plugins(marketplace_slug: str, request: Request):
    with get_connection() as conn:
        _get_marketplace_or_404(conn, marketplace_slug)
        require_marketplace_read(conn, _actor(request), marketplace_slug)
        rows = conn.execute(
            select(plugins).where(plugins.c.marketplace_slug == marketplace_slug).order_by(plugins.c.slug)
        ).mappings().all()
        return [_plugin_out(row, conn) for row in rows]


@router.post("", response_model=PluginOut, status_code=201)
def create_plugin(marketplace_slug: str, body: PluginCreate, request: Request):
    plugin_slug = make_slug(body.displayName)
    now = int(time.time())
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        require_marketplace_write(conn, _actor(request), marketplace_slug)
        existing = conn.execute(
            select(plugins.c.slug).where(
                plugins.c.marketplace_slug == marketplace_slug,
                plugins.c.slug == plugin_slug,
            )
        ).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Plugin slug '{plugin_slug}' already exists")

    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(insert(plugins).values(
                    marketplace_slug=marketplace_slug,
                    slug=plugin_slug,
                    display_name=body.displayName,
                    description=body.description,
                    version="1.0.0",
                    created_at=now,
                    updated_at=now,
                ))
                _sync_plugin(conn, marketplace_slug, plugin_slug, f"Add plugin: {plugin_slug}")
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise

    with get_connection() as conn:
        row = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        return _plugin_out(row, conn)


@router.get("/{plugin_slug}", response_model=PluginOut)
def get_plugin(marketplace_slug: str, plugin_slug: str, request: Request):
    with get_connection() as conn:
        _get_marketplace_or_404(conn, marketplace_slug)
        require_marketplace_read(conn, _actor(request), marketplace_slug)
        row = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        return _plugin_out(row, conn)


@router.put("/{plugin_slug}", response_model=PluginOut)
def update_plugin(marketplace_slug: str, plugin_slug: str, body: PluginUpdate, request: Request):
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        current = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_write(conn, _actor(request), marketplace_slug, plugin_slug)
    updates: dict[str, Any] = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.description is not None:
        updates["description"] = body.description
    if not updates:
        with get_connection() as conn:
            return _plugin_out(current, conn)
    updates["updated_at"] = int(time.time())
    updates["version"] = _bump_version(current["version"])
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(
                    update(plugins).where(
                        plugins.c.marketplace_slug == marketplace_slug,
                        plugins.c.slug == plugin_slug,
                    ).values(**updates)
                )
                _sync_plugin(conn, marketplace_slug, plugin_slug, f"Update plugin: {plugin_slug}")
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise
    with get_connection() as conn:
        return _plugin_out(_get_plugin_or_404(conn, marketplace_slug, plugin_slug), conn)


@router.delete("/{plugin_slug}", status_code=204)
def delete_plugin(marketplace_slug: str, plugin_slug: str, request: Request):
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_maintain(conn, _actor(request), marketplace_slug)
        removal = write_path.remove_plugin_files(plugin_slug, conn, marketplace_slug)
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(
                    delete(plugins).where(
                        plugins.c.marketplace_slug == marketplace_slug,
                        plugins.c.slug == plugin_slug,
                    )
                )
                write_path.sync_and_commit(
                    marketplace_slug,
                    conn,
                    commit_message=f"Delete plugin: {plugin_slug}",
                    extra_files=removal,
                )
                record_audit(conn, _actor(request), "plugin.delete", "plugin", f"{marketplace_slug}/{plugin_slug}")
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise


@router.get("/{plugin_slug}/skills", response_model=list[SkillOut])
def list_plugin_skills(marketplace_slug: str, plugin_slug: str, request: Request):
    with get_connection() as conn:
        _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_read(conn, _actor(request), marketplace_slug)
        rows = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
            ).order_by(skills.c.slug)
        ).mappings().all()
        return [_skill_out(row, include_content=False) for row in rows]


@router.post("/{plugin_slug}/skills", response_model=SkillOut, status_code=201)
def create_plugin_skill(marketplace_slug: str, plugin_slug: str, body: SkillCreate, request: Request):
    skill_slug = make_slug(body.displayName)
    now = int(time.time())
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        plugin = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_write(conn, _actor(request), marketplace_slug, plugin_slug)
        existing = conn.execute(
            select(skills.c.slug).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
                skills.c.slug == skill_slug,
            )
        ).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Skill slug '{skill_slug}' already exists")
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(insert(skills).values(
                    marketplace_slug=marketplace_slug,
                    plugin_slug=plugin_slug,
                    slug=skill_slug,
                    display_name=body.displayName,
                    description=body.description,
                    version="1.0.0",
                    content=body.content,
                    created_at=now,
                    updated_at=now,
                ))
                new_version = _bump_version(plugin["version"])
                conn.execute(
                    update(plugins).where(
                        plugins.c.marketplace_slug == marketplace_slug,
                        plugins.c.slug == plugin_slug,
                    ).values(version=new_version, updated_at=now)
                )
                sha = _sync_plugin(conn, marketplace_slug, plugin_slug, f"Add skill: {skill_slug}")
                conn.execute(
                    update(skills).where(
                        skills.c.marketplace_slug == marketplace_slug,
                        skills.c.plugin_slug == plugin_slug,
                        skills.c.slug == skill_slug,
                    ).values(last_commit=sha)
                )
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise
    with get_connection() as conn:
        row = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one()
        return _skill_out(row)


@router.get("/{plugin_slug}/skills/{skill_slug}", response_model=SkillOut)
def get_plugin_skill(marketplace_slug: str, plugin_slug: str, skill_slug: str, request: Request):
    with get_connection() as conn:
        _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_read(conn, _actor(request), marketplace_slug)
        row = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Skill not found")
        return _skill_out(row)


@router.put("/{plugin_slug}/skills/{skill_slug}", response_model=SkillOut)
def update_plugin_skill(marketplace_slug: str, plugin_slug: str, skill_slug: str, body: SkillUpdate, request: Request):
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        plugin = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_write(conn, _actor(request), marketplace_slug, plugin_slug)
        skill = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one_or_none()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    updates: dict[str, Any] = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.description is not None:
        updates["description"] = body.description
    if body.content is not None:
        updates["content"] = body.content
    if not updates:
        return _skill_out(skill)
    now = int(time.time())
    updates["updated_at"] = now
    updates["version"] = _bump_version(skill["version"])
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(
                    update(skills).where(
                        skills.c.marketplace_slug == marketplace_slug,
                        skills.c.plugin_slug == plugin_slug,
                        skills.c.slug == skill_slug,
                    ).values(**updates)
                )
                conn.execute(
                    update(plugins).where(
                        plugins.c.marketplace_slug == marketplace_slug,
                        plugins.c.slug == plugin_slug,
                    ).values(version=_bump_version(plugin["version"]), updated_at=now)
                )
                sha = _sync_plugin(conn, marketplace_slug, plugin_slug, f"Update skill: {skill_slug}")
                conn.execute(
                    update(skills).where(
                        skills.c.marketplace_slug == marketplace_slug,
                        skills.c.plugin_slug == plugin_slug,
                        skills.c.slug == skill_slug,
                    ).values(last_commit=sha)
                )
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise
    with get_connection() as conn:
        row = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one()
        return _skill_out(row)


@router.delete("/{plugin_slug}/skills/{skill_slug}", status_code=204)
def delete_plugin_skill(marketplace_slug: str, plugin_slug: str, skill_slug: str, request: Request):
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        plugin = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_maintain(conn, _actor(request), marketplace_slug)
        existing = conn.execute(
            select(skills.c.slug).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
                skills.c.slug == skill_slug,
            )
        ).one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    now = int(time.time())
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(delete(skills).where(
                    skills.c.marketplace_slug == marketplace_slug,
                    skills.c.plugin_slug == plugin_slug,
                    skills.c.slug == skill_slug,
                ))
                conn.execute(update(plugins).where(
                    plugins.c.marketplace_slug == marketplace_slug,
                    plugins.c.slug == plugin_slug,
                ).values(version=_bump_version(plugin["version"]), updated_at=now))
                _sync_plugin(
                    conn,
                    marketplace_slug,
                    plugin_slug,
                    f"Delete skill: {skill_slug}",
                    extra_files={f"plugins/{plugin_slug}/skills/{skill_slug}/SKILL.md": None},
                )
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise


@router.get("/{plugin_slug}/hooks", response_model=list[HookOut])
def list_hooks(marketplace_slug: str, plugin_slug: str, request: Request):
    return _list_component(marketplace_slug, plugin_slug, plugin_hooks, _hook_out, request)


@router.post("/{plugin_slug}/hooks", response_model=HookOut, status_code=201)
def create_hook(marketplace_slug: str, plugin_slug: str, body: HookCreate, request: Request):
    return _create_hook(marketplace_slug, plugin_slug, body, request)


@router.put("/{plugin_slug}/hooks/{component_slug}", response_model=HookOut)
def update_hook(marketplace_slug: str, plugin_slug: str, component_slug: str, body: HookUpdate, request: Request):
    updates: dict[str, Any] = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.event is not None:
        updates["event"] = body.event
    if body.matcher is not None:
        updates["matcher"] = body.matcher
    if body.handler is not None:
        updates["handler_json"] = body.handler.model_dump_json(exclude_none=True)
    return _update_component(marketplace_slug, plugin_slug, component_slug, plugin_hooks, updates, f"Update hook: {component_slug}", _hook_out, request)


@router.delete("/{plugin_slug}/hooks/{component_slug}", status_code=204)
def delete_hook(marketplace_slug: str, plugin_slug: str, component_slug: str, request: Request):
    _delete_component(marketplace_slug, plugin_slug, component_slug, plugin_hooks, f"Delete hook: {component_slug}", request=request)


@router.get("/{plugin_slug}/agents", response_model=list[AgentOut])
def list_agents(marketplace_slug: str, plugin_slug: str, request: Request):
    return _list_component(marketplace_slug, plugin_slug, plugin_agents, _agent_out, request)


@router.post("/{plugin_slug}/agents", response_model=AgentOut, status_code=201)
def create_agent(marketplace_slug: str, plugin_slug: str, body: AgentCreate, request: Request):
    slug = make_slug(body.displayName)
    now = int(time.time())
    return _insert_component(
        marketplace_slug,
        plugin_slug,
        slug,
        plugin_agents,
        {
            "slug": slug,
            "display_name": body.displayName,
            "description": body.description,
            "config_json": json.dumps(body.config),
            "prompt": body.prompt,
            "created_at": now,
            "updated_at": now,
        },
        f"Add agent: {slug}",
        _agent_out,
        request,
    )


@router.put("/{plugin_slug}/agents/{component_slug}", response_model=AgentOut)
def update_agent(marketplace_slug: str, plugin_slug: str, component_slug: str, body: AgentUpdate, request: Request):
    updates: dict[str, Any] = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.description is not None:
        updates["description"] = body.description
    if body.prompt is not None:
        updates["prompt"] = body.prompt
    if body.config is not None:
        updates["config_json"] = json.dumps(body.config)
    return _update_component(marketplace_slug, plugin_slug, component_slug, plugin_agents, updates, f"Update agent: {component_slug}", _agent_out, request)


@router.delete("/{plugin_slug}/agents/{component_slug}", status_code=204)
def delete_agent(marketplace_slug: str, plugin_slug: str, component_slug: str, request: Request):
    _delete_component(
        marketplace_slug,
        plugin_slug,
        component_slug,
        plugin_agents,
        f"Delete agent: {component_slug}",
        {f"plugins/{plugin_slug}/agents/{component_slug}.md": None},
        request,
    )


@router.get("/{plugin_slug}/mcp-servers", response_model=list[McpServerOut])
def list_mcp_servers(marketplace_slug: str, plugin_slug: str, request: Request):
    return _list_component(marketplace_slug, plugin_slug, plugin_mcp_servers, _mcp_out, request)


@router.post("/{plugin_slug}/mcp-servers", response_model=McpServerOut, status_code=201)
def create_mcp_server(marketplace_slug: str, plugin_slug: str, body: McpServerCreate, request: Request):
    slug = make_slug(body.displayName)
    now = int(time.time())
    return _insert_component(
        marketplace_slug,
        plugin_slug,
        slug,
        plugin_mcp_servers,
        {
            "slug": slug,
            "display_name": body.displayName,
            "config_json": json.dumps(body.config),
            "created_at": now,
            "updated_at": now,
        },
        f"Add MCP server: {slug}",
        _mcp_out,
        request,
    )


@router.put("/{plugin_slug}/mcp-servers/{component_slug}", response_model=McpServerOut)
def update_mcp_server(marketplace_slug: str, plugin_slug: str, component_slug: str, body: McpServerUpdate, request: Request):
    updates: dict[str, Any] = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.config is not None:
        updates["config_json"] = json.dumps(body.config)
    return _update_component(marketplace_slug, plugin_slug, component_slug, plugin_mcp_servers, updates, f"Update MCP server: {component_slug}", _mcp_out, request)


@router.delete("/{plugin_slug}/mcp-servers/{component_slug}", status_code=204)
def delete_mcp_server(marketplace_slug: str, plugin_slug: str, component_slug: str, request: Request):
    _delete_component(marketplace_slug, plugin_slug, component_slug, plugin_mcp_servers, f"Delete MCP server: {component_slug}", request=request)


@router.get("/{plugin_slug}/commands", response_model=list[CommandOut])
def list_commands(marketplace_slug: str, plugin_slug: str, request: Request):
    return _list_component(marketplace_slug, plugin_slug, plugin_commands, _command_out, request)


@router.post("/{plugin_slug}/commands", response_model=CommandOut, status_code=201)
def create_command(marketplace_slug: str, plugin_slug: str, body: CommandCreate, request: Request):
    slug = make_slug(body.displayName)
    now = int(time.time())
    return _insert_component(
        marketplace_slug,
        plugin_slug,
        slug,
        plugin_commands,
        {
            "slug": slug,
            "display_name": body.displayName,
            "description": body.description,
            "content": body.content,
            "created_at": now,
            "updated_at": now,
        },
        f"Add command: {slug}",
        _command_out,
        request,
    )


@router.put("/{plugin_slug}/commands/{component_slug}", response_model=CommandOut)
def update_command(marketplace_slug: str, plugin_slug: str, component_slug: str, body: CommandUpdate, request: Request):
    updates: dict[str, Any] = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.description is not None:
        updates["description"] = body.description
    if body.content is not None:
        updates["content"] = body.content
    return _update_component(marketplace_slug, plugin_slug, component_slug, plugin_commands, updates, f"Update command: {component_slug}", _command_out, request)


@router.delete("/{plugin_slug}/commands/{component_slug}", status_code=204)
def delete_command(marketplace_slug: str, plugin_slug: str, component_slug: str, request: Request):
    _delete_component(
        marketplace_slug,
        plugin_slug,
        component_slug,
        plugin_commands,
        f"Delete command: {component_slug}",
        {f"plugins/{plugin_slug}/commands/{component_slug}.md": None},
        request,
    )


@router.get("/{plugin_slug}/monitors", response_model=list[MonitorOut])
def list_monitors(marketplace_slug: str, plugin_slug: str, request: Request):
    return _list_component(marketplace_slug, plugin_slug, plugin_monitors, _monitor_out, request)


@router.post("/{plugin_slug}/monitors", response_model=MonitorOut, status_code=201)
def create_monitor(marketplace_slug: str, plugin_slug: str, body: MonitorCreate, request: Request):
    slug = make_slug(body.displayName)
    now = int(time.time())
    return _insert_component(
        marketplace_slug,
        plugin_slug,
        slug,
        plugin_monitors,
        {
            "slug": slug,
            "display_name": body.displayName,
            "command": body.command,
            "description": body.description,
            "when": body.when,
            "created_at": now,
            "updated_at": now,
        },
        f"Add monitor: {slug}",
        _monitor_out,
        request,
    )


@router.put("/{plugin_slug}/monitors/{component_slug}", response_model=MonitorOut)
def update_monitor(marketplace_slug: str, plugin_slug: str, component_slug: str, body: MonitorUpdate, request: Request):
    updates: dict[str, Any] = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.command is not None:
        updates["command"] = body.command
    if body.description is not None:
        updates["description"] = body.description
    if body.when is not None:
        updates["when"] = body.when
    return _update_component(marketplace_slug, plugin_slug, component_slug, plugin_monitors, updates, f"Update monitor: {component_slug}", _monitor_out, request)


@router.delete("/{plugin_slug}/monitors/{component_slug}", status_code=204)
def delete_monitor(marketplace_slug: str, plugin_slug: str, component_slug: str, request: Request):
    _delete_component(marketplace_slug, plugin_slug, component_slug, plugin_monitors, f"Delete monitor: {component_slug}", request=request)


@router.get("/{plugin_slug}/settings", response_model=PluginSettingsOut)
def get_settings(marketplace_slug: str, plugin_slug: str, request: Request):
    with get_connection() as conn:
        _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_read(conn, _actor(request), marketplace_slug)
        row = conn.execute(select(plugin_settings).where(
            plugin_settings.c.marketplace_slug == marketplace_slug,
            plugin_settings.c.plugin_slug == plugin_slug,
        )).mappings().one_or_none()
        if row is None:
            return {"marketplaceSlug": marketplace_slug, "pluginSlug": plugin_slug, "settings": {}, "updatedAt": 0}
        return {"marketplaceSlug": marketplace_slug, "pluginSlug": plugin_slug, "settings": _json_out(row["settings_json"]), "updatedAt": row["updated_at"]}


@router.put("/{plugin_slug}/settings", response_model=PluginSettingsOut)
def put_settings(marketplace_slug: str, plugin_slug: str, body: PluginSettingsIn, request: Request):
    now = int(time.time())
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        plugin = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_write(conn, _actor(request), marketplace_slug, plugin_slug)
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                existing = conn.execute(select(plugin_settings).where(
                    plugin_settings.c.marketplace_slug == marketplace_slug,
                    plugin_settings.c.plugin_slug == plugin_slug,
                )).one_or_none()
                values = {"settings_json": json.dumps(body.settings), "updated_at": now}
                if existing:
                    conn.execute(update(plugin_settings).where(
                        plugin_settings.c.marketplace_slug == marketplace_slug,
                        plugin_settings.c.plugin_slug == plugin_slug,
                    ).values(**values))
                else:
                    conn.execute(insert(plugin_settings).values(
                        marketplace_slug=marketplace_slug,
                        plugin_slug=plugin_slug,
                        **values,
                    ))
                conn.execute(update(plugins).where(
                    plugins.c.marketplace_slug == marketplace_slug,
                    plugins.c.slug == plugin_slug,
                ).values(version=_bump_version(plugin["version"]), updated_at=now))
                _sync_plugin(conn, marketplace_slug, plugin_slug, "Update plugin settings")
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise
    return get_settings(marketplace_slug, plugin_slug, request)


def _list_component(marketplace_slug: str, plugin_slug: str, table, out_fn, request: Request):
    with get_connection() as conn:
        _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_read(conn, _actor(request), marketplace_slug)
        rows = conn.execute(select(table).where(
            table.c.marketplace_slug == marketplace_slug,
            table.c.plugin_slug == plugin_slug,
        ).order_by(table.c.slug)).mappings().all()
        return [out_fn(row) for row in rows]


def _insert_component(marketplace_slug: str, plugin_slug: str, slug: str, table, values: dict[str, Any], message: str, out_fn, request: Request):
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        plugin = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_write(conn, _actor(request), marketplace_slug, plugin_slug)
        existing = conn.execute(select(table.c.slug).where(
            table.c.marketplace_slug == marketplace_slug,
            table.c.plugin_slug == plugin_slug,
            table.c.slug == slug,
        )).one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Component slug '{slug}' already exists")
    now = int(time.time())
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(insert(table).values(marketplace_slug=marketplace_slug, plugin_slug=plugin_slug, **values))
                conn.execute(update(plugins).where(
                    plugins.c.marketplace_slug == marketplace_slug,
                    plugins.c.slug == plugin_slug,
                ).values(version=_bump_version(plugin["version"]), updated_at=now))
                _sync_plugin(conn, marketplace_slug, plugin_slug, message)
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise
    with get_connection() as conn:
        row = conn.execute(select(table).where(
            table.c.marketplace_slug == marketplace_slug,
            table.c.plugin_slug == plugin_slug,
            table.c.slug == slug,
        )).mappings().one()
        return out_fn(row)


def _delete_component(
    marketplace_slug: str,
    plugin_slug: str,
    component_slug: str,
    table,
    message: str,
    extra_files: dict[str, None] | None = None,
    request: Request | None = None,
) -> None:
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        plugin = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_maintain(conn, _actor(request) if request else None, marketplace_slug)
        existing = conn.execute(select(table.c.slug).where(
            table.c.marketplace_slug == marketplace_slug,
            table.c.plugin_slug == plugin_slug,
            table.c.slug == component_slug,
        )).one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Component not found")
    now = int(time.time())
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(delete(table).where(
                    table.c.marketplace_slug == marketplace_slug,
                    table.c.plugin_slug == plugin_slug,
                    table.c.slug == component_slug,
                ))
                conn.execute(update(plugins).where(
                    plugins.c.marketplace_slug == marketplace_slug,
                    plugins.c.slug == plugin_slug,
                ).values(version=_bump_version(plugin["version"]), updated_at=now))
                _sync_plugin(conn, marketplace_slug, plugin_slug, message, extra_files=extra_files)
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise


def _update_component(marketplace_slug: str, plugin_slug: str, component_slug: str, table, updates: dict[str, Any], message: str, out_fn, request: Request):
    with get_connection() as conn:
        mkt = _get_marketplace_or_404(conn, marketplace_slug)
        plugin = _get_plugin_or_404(conn, marketplace_slug, plugin_slug)
        require_marketplace_write(conn, _actor(request), marketplace_slug, plugin_slug)
        current = conn.execute(select(table).where(
            table.c.marketplace_slug == marketplace_slug,
            table.c.plugin_slug == plugin_slug,
            table.c.slug == component_slug,
        )).mappings().one_or_none()
    if current is None:
        raise HTTPException(status_code=404, detail="Component not found")
    if not updates:
        return out_fn(current)
    now = int(time.time())
    updates["updated_at"] = now
    with marketplace_write_lock(marketplace_slug):
        try:
            with get_transaction() as conn:
                conn.execute(update(table).where(
                    table.c.marketplace_slug == marketplace_slug,
                    table.c.plugin_slug == plugin_slug,
                    table.c.slug == component_slug,
                ).values(**updates))
                conn.execute(update(plugins).where(
                    plugins.c.marketplace_slug == marketplace_slug,
                    plugins.c.slug == plugin_slug,
                ).values(version=_bump_version(plugin["version"]), updated_at=now))
                _sync_plugin(conn, marketplace_slug, plugin_slug, message)
        except Exception:
            git_store.reset_working_tree(marketplace_slug)
            raise
    with get_connection() as conn:
        row = conn.execute(select(table).where(
            table.c.marketplace_slug == marketplace_slug,
            table.c.plugin_slug == plugin_slug,
            table.c.slug == component_slug,
        )).mappings().one()
        return out_fn(row)


def _create_hook(marketplace_slug: str, plugin_slug: str, body: HookCreate, request: Request):
    slug = make_slug(body.displayName)
    now = int(time.time())
    return _insert_component(
        marketplace_slug,
        plugin_slug,
        slug,
        plugin_hooks,
        {
            "slug": slug,
            "display_name": body.displayName,
            "event": body.event,
            "matcher": body.matcher,
            "handler_json": body.handler.model_dump_json(exclude_none=True),
            "created_at": now,
            "updated_at": now,
        },
        f"Add hook: {slug}",
        _hook_out,
        request,
    )


def _hook_out(row) -> dict[str, Any]:
    return {
        "marketplaceSlug": row["marketplace_slug"],
        "pluginSlug": row["plugin_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "event": row["event"],
        "matcher": row["matcher"],
        "handler": _json_out(row["handler_json"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _agent_out(row) -> dict[str, Any]:
    return {
        "marketplaceSlug": row["marketplace_slug"],
        "pluginSlug": row["plugin_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "description": row["description"],
        "config": _json_out(row["config_json"]),
        "prompt": row["prompt"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _mcp_out(row) -> dict[str, Any]:
    return {
        "marketplaceSlug": row["marketplace_slug"],
        "pluginSlug": row["plugin_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "config": _json_out(row["config_json"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _command_out(row) -> dict[str, Any]:
    return {
        "marketplaceSlug": row["marketplace_slug"],
        "pluginSlug": row["plugin_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "description": row["description"],
        "content": row["content"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _monitor_out(row) -> dict[str, Any]:
    return {
        "marketplaceSlug": row["marketplace_slug"],
        "pluginSlug": row["plugin_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "command": row["command"],
        "description": row["description"],
        "when": row["when"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
