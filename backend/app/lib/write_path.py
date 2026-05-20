"""
The canonical write path (§9) — shared by all mutating API operations.

Every mutation that touches the git store must go through one of these helpers
so atomicity between SQLite and the git repo is guaranteed.
"""
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.lib import git_store, marketplace_json
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
    users,
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def _marketplace_author(marketplace_slug: str, conn: Connection) -> tuple[str, str]:
    """Return (name, email) for the user who created this marketplace."""
    row = conn.execute(
        select(users.c.display_name, users.c.email)
        .select_from(marketplaces.outerjoin(users, marketplaces.c.created_by_user_id == users.c.id))
        .where(marketplaces.c.slug == marketplace_slug)
    ).mappings().one_or_none()
    if row and row["display_name"]:
        return row["display_name"], row["email"] or ""
    return "SkillShelf", "noreply@skillshelf"


def _claude_plugin_json(
    plugin_slug: str,
    display_name: str,
    description: str,
    version: str,
    owner_name: str,
    owner_email: str,
    components: dict[str, bool],
) -> str:
    manifest: dict[str, Any] = {
        "name": plugin_slug,
        "displayName": display_name,
        "description": description,
        "version": version,
        "author": {
            "name": owner_name,
            "email": owner_email,
        },
    }
    if components["skills"]:
        manifest["skills"] = "./skills/"
    if components["commands"]:
        manifest["commands"] = "./commands/"
    if components["agents"]:
        manifest["agents"] = "./agents/"
    if components["hooks"]:
        manifest["hooks"] = "./hooks/hooks.json"
    if components["mcp"]:
        manifest["mcpServers"] = "./.mcp.json"
    if components["monitors"]:
        manifest["experimental"] = {"monitors": "./monitors/monitors.json"}
    return _json(manifest)


def _codex_plugin_json(
    plugin_slug: str,
    display_name: str,
    description: str,
    version: str,
) -> str:
    return _json({
        "name": plugin_slug,
        "version": version,
        "description": description,
        "skills": "./skills/",
        "interface": {
            "displayName": display_name,
            "shortDescription": description,
            "longDescription": description,
            "category": "Productivity",
            "capabilities": ["Skills"],
        },
    })


def _skill_md(slug: str, description: str, content: str) -> str:
    return f"---\nname: {slug}\ndescription: {description}\n---\n{content}\n"



def build_plugin_files(marketplace_slug: str, plugin_slug: str, conn: Connection) -> dict[str, str | None]:
    """Return every rendered file for a multi-capability plugin."""
    plugin = conn.execute(
        select(plugins).where(
            plugins.c.marketplace_slug == marketplace_slug,
            plugins.c.slug == plugin_slug,
        )
    ).mappings().one()
    author_name, author_email = _marketplace_author(marketplace_slug, conn)

    skill_rows = conn.execute(
        select(skills).where(
            skills.c.marketplace_slug == marketplace_slug,
            skills.c.plugin_slug == plugin_slug,
        ).order_by(skills.c.slug)
    ).mappings().all()
    hook_rows = conn.execute(
        select(plugin_hooks).where(
            plugin_hooks.c.marketplace_slug == marketplace_slug,
            plugin_hooks.c.plugin_slug == plugin_slug,
        ).order_by(plugin_hooks.c.slug)
    ).mappings().all()
    agent_rows = conn.execute(
        select(plugin_agents).where(
            plugin_agents.c.marketplace_slug == marketplace_slug,
            plugin_agents.c.plugin_slug == plugin_slug,
        ).order_by(plugin_agents.c.slug)
    ).mappings().all()
    mcp_rows = conn.execute(
        select(plugin_mcp_servers).where(
            plugin_mcp_servers.c.marketplace_slug == marketplace_slug,
            plugin_mcp_servers.c.plugin_slug == plugin_slug,
        ).order_by(plugin_mcp_servers.c.slug)
    ).mappings().all()
    command_rows = conn.execute(
        select(plugin_commands).where(
            plugin_commands.c.marketplace_slug == marketplace_slug,
            plugin_commands.c.plugin_slug == plugin_slug,
        ).order_by(plugin_commands.c.slug)
    ).mappings().all()
    monitor_rows = conn.execute(
        select(plugin_monitors).where(
            plugin_monitors.c.marketplace_slug == marketplace_slug,
            plugin_monitors.c.plugin_slug == plugin_slug,
        ).order_by(plugin_monitors.c.slug)
    ).mappings().all()
    settings_row = conn.execute(
        select(plugin_settings).where(
            plugin_settings.c.marketplace_slug == marketplace_slug,
            plugin_settings.c.plugin_slug == plugin_slug,
        )
    ).mappings().one_or_none()

    components = {
        "skills": bool(skill_rows),
        "commands": bool(command_rows),
        "agents": bool(agent_rows),
        "hooks": bool(hook_rows),
        "mcp": bool(mcp_rows),
        "monitors": bool(monitor_rows),
    }
    base = f"plugins/{plugin_slug}"
    files: dict[str, str | None] = {
        f"{base}/.claude-plugin/plugin.json": _claude_plugin_json(
            plugin_slug,
            plugin["display_name"],
            plugin["description"],
            plugin["version"],
            author_name,
            author_email,
            components,
        )
    }

    if skill_rows:
        files[f"{base}/.codex-plugin/plugin.json"] = _codex_plugin_json(
            plugin_slug,
            plugin["display_name"],
            plugin["description"],
            plugin["version"],
        )
    else:
        files[f"{base}/.codex-plugin/plugin.json"] = None

    for skill in skill_rows:
        files[f"{base}/skills/{skill['slug']}/SKILL.md"] = _skill_md(
            skill["slug"],
            skill["description"],
            skill["content"],
        )
    if hook_rows:
        files[f"{base}/hooks/hooks.json"] = _json(_hooks_json(hook_rows))
    else:
        files[f"{base}/hooks/hooks.json"] = None
    if agent_rows:
        for agent in agent_rows:
            files[f"{base}/agents/{agent['slug']}.md"] = _agent_md(agent)
    if mcp_rows:
        files[f"{base}/.mcp.json"] = _json({
            "mcpServers": {
                row["slug"]: json.loads(row["config_json"])
                for row in mcp_rows
            }
        })
    else:
        files[f"{base}/.mcp.json"] = None
    if command_rows:
        for command in command_rows:
            files[f"{base}/commands/{command['slug']}.md"] = _command_md(command)
    if monitor_rows:
        files[f"{base}/monitors/monitors.json"] = _json([
            _monitor_json(row) for row in monitor_rows
        ])
    else:
        files[f"{base}/monitors/monitors.json"] = None
    if settings_row is not None:
        files[f"{base}/settings.json"] = _json(json.loads(settings_row["settings_json"]))
    else:
        files[f"{base}/settings.json"] = None
    return files


def remove_plugin_files(plugin_slug: str, conn: Connection, marketplace_slug: str | None = None) -> dict[str, None]:
    """Return deletion entries for all files belonging to a plugin."""
    files: dict[str, None] = {}
    if marketplace_slug is not None:
        for row in conn.execute(
            select(skills.c.slug).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.plugin_slug == plugin_slug,
            )
        ).mappings():
            files[f"plugins/{plugin_slug}/skills/{row['slug']}/SKILL.md"] = None
        for row in conn.execute(
            select(plugin_agents.c.slug).where(
                plugin_agents.c.marketplace_slug == marketplace_slug,
                plugin_agents.c.plugin_slug == plugin_slug,
            )
        ).mappings():
            files[f"plugins/{plugin_slug}/agents/{row['slug']}.md"] = None
        for row in conn.execute(
            select(plugin_commands.c.slug).where(
                plugin_commands.c.marketplace_slug == marketplace_slug,
                plugin_commands.c.plugin_slug == plugin_slug,
            )
        ).mappings():
            files[f"plugins/{plugin_slug}/commands/{row['slug']}.md"] = None
    for rel in [
        f"plugins/{plugin_slug}/.claude-plugin/plugin.json",
        f"plugins/{plugin_slug}/.codex-plugin/plugin.json",
        f"plugins/{plugin_slug}/hooks/hooks.json",
        f"plugins/{plugin_slug}/.mcp.json",
        f"plugins/{plugin_slug}/monitors/monitors.json",
        f"plugins/{plugin_slug}/settings.json",
    ]:
        files[rel] = None
    return files


def _hooks_json(rows) -> dict[str, Any]:
    result: dict[str, Any] = {"hooks": {}}
    for row in rows:
        entry: dict[str, Any] = {
            "hooks": [json.loads(row["handler_json"])],
        }
        if row["matcher"]:
            entry["matcher"] = row["matcher"]
        result["hooks"].setdefault(row["event"], []).append(entry)
    return result


def _yaml_scalar(value: Any) -> str:
    return json.dumps(value)


def _agent_md(row) -> str:
    config = json.loads(row["config_json"])
    frontmatter = {
        "name": row["slug"],
        "description": row["description"],
        **config,
    }
    lines = ["---"]
    for key, value in frontmatter.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    lines.append(row["prompt"])
    return "\n".join(lines) + "\n"


def _command_md(row) -> str:
    return f"---\ndescription: {_yaml_scalar(row['description'])}\n---\n{row['content']}\n"


def _monitor_json(row) -> dict[str, Any]:
    data = {
        "name": row["slug"],
        "command": row["command"],
        "description": row["description"],
    }
    if row["when"]:
        data["when"] = row["when"]
    return data



def sync_and_commit(
    marketplace_slug: str,
    conn: Connection,
    commit_message: str,
    extra_files: dict[str, str | None] | None = None,
) -> str:
    """
    Steps 4–7 of the canonical write path.

    Regenerates marketplace.json, applies any extra file changes, commits
    everything atomically, and returns the commit SHA.

    The caller is responsible for the surrounding SQLAlchemy transaction
    (steps 2–3 and 8). On exception here, the caller should roll back and call
    git_store.reset_working_tree().
    """
    author_name, author_email = _marketplace_author(marketplace_slug, conn)

    # Step 5: regenerate marketplace files (always full rewrite)
    files: dict[str, str | None] = {
        ".claude-plugin/marketplace.json": marketplace_json.serialize_marketplace_json(marketplace_slug, conn),
        ".agents/plugins/marketplace.json": marketplace_json.serialize_codex_marketplace_json(marketplace_slug, conn),
    }

    # Step 4: apply extra file changes (skill writes or removals)
    if extra_files:
        files.update(extra_files)

    git_store.write_files(marketplace_slug, files)

    # Step 6: single atomic commit
    sha = git_store.commit(
        marketplace_slug,
        commit_message,
        author_name,
        author_email,
    )
    return sha
