import json
import time

from sqlalchemy import create_engine, insert

from app.lib.write_path import build_plugin_files
from app.models import (
    marketplaces,
    metadata,
    plugin_agents,
    plugin_commands,
    plugin_hooks,
    plugin_mcp_servers,
    plugin_monitors,
    plugin_settings,
    plugins,
    skills,
)


def test_build_plugin_files_renders_guided_components():
    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    now = int(time.time())
    with engine.connect() as conn:
        conn.execute(insert(marketplaces).values(
            slug="finance-team",
            display_name="Finance Team",
            owner_name="Alice",
            owner_email="alice@example.com",
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(plugins).values(
            marketplace_slug="finance-team",
            slug="ops-toolkit",
            display_name="Ops Toolkit",
            description="Operational helpers",
            version="1.2.3",
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(skills).values(
            marketplace_slug="finance-team",
            plugin_slug="ops-toolkit",
            slug="triage",
            display_name="Triage",
            description="Triage incidents",
            version="1.0.0",
            content="Follow the incident checklist.",
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(plugin_hooks).values(
            marketplace_slug="finance-team",
            plugin_slug="ops-toolkit",
            slug="format-on-edit",
            display_name="Format on edit",
            event="PostToolUse",
            matcher="Write|Edit",
            handler_json=json.dumps({"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh", "timeout": 30}),
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(plugin_agents).values(
            marketplace_slug="finance-team",
            plugin_slug="ops-toolkit",
            slug="reviewer",
            display_name="Reviewer",
            description="Reviews operational changes",
            config_json=json.dumps({"model": "sonnet", "maxTurns": 5}),
            prompt="Review the change.",
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(plugin_mcp_servers).values(
            marketplace_slug="finance-team",
            plugin_slug="ops-toolkit",
            slug="status-api",
            display_name="Status API",
            config_json=json.dumps({"type": "http", "url": "https://status.example.com/mcp"}),
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(plugin_commands).values(
            marketplace_slug="finance-team",
            plugin_slug="ops-toolkit",
            slug="deploy",
            display_name="Deploy",
            description="Deploy safely",
            content="Deploy with $ARGUMENTS.",
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(plugin_monitors).values(
            marketplace_slug="finance-team",
            plugin_slug="ops-toolkit",
            slug="error-log",
            display_name="Error log",
            command="tail -F ./logs/error.log",
            description="Application error log",
            when="always",
            created_at=now,
            updated_at=now,
        ))
        conn.execute(insert(plugin_settings).values(
            marketplace_slug="finance-team",
            plugin_slug="ops-toolkit",
            settings_json=json.dumps({"agent": "reviewer"}),
            updated_at=now,
        ))

        files = build_plugin_files("finance-team", "ops-toolkit", conn)

    manifest = json.loads(files["plugins/ops-toolkit/.claude-plugin/plugin.json"])
    assert manifest["name"] == "ops-toolkit"
    assert manifest["skills"] == "./skills/"
    assert manifest["hooks"] == "./hooks/hooks.json"
    assert manifest["agents"] == "./agents/"
    assert manifest["mcpServers"] == "./.mcp.json"
    assert manifest["commands"] == "./commands/"
    assert manifest["experimental"]["monitors"] == "./monitors/monitors.json"
    assert "Follow the incident checklist." in files["plugins/ops-toolkit/skills/triage/SKILL.md"]
    assert json.loads(files["plugins/ops-toolkit/hooks/hooks.json"])["hooks"]["PostToolUse"][0]["matcher"] == "Write|Edit"
    assert "maxTurns: 5" in files["plugins/ops-toolkit/agents/reviewer.md"]
    assert json.loads(files["plugins/ops-toolkit/.mcp.json"])["mcpServers"]["status-api"]["type"] == "http"
    assert "Deploy with $ARGUMENTS." in files["plugins/ops-toolkit/commands/deploy.md"]
    assert json.loads(files["plugins/ops-toolkit/monitors/monitors.json"])[0]["name"] == "error-log"
    assert json.loads(files["plugins/ops-toolkit/settings.json"])["agent"] == "reviewer"
    assert json.loads(files["plugins/ops-toolkit/.codex-plugin/plugin.json"])["skills"] == "./skills/"
