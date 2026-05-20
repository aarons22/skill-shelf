"""Integration tests for the API routes — uses FastAPI's TestClient (no real server)."""
import os

import pytest
from fastapi.testclient import TestClient

# Point at a temp DB before importing the app
@pytest.fixture(autouse=True, scope="module")
def temp_env(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    os.environ["SKILLSHELF_DATA_DIR"] = str(data_dir)
    os.environ["PUBLIC_BASE_URL"] = "http://testserver"
    os.makedirs(os.path.join(str(data_dir), "marketplaces"), exist_ok=True)

    from app import config as cfg
    cfg.get_settings.cache_clear()

    # Patch the DB engine to use the temp path
    import app.db as db_module
    db_module._engine = None

    yield

    cfg.get_settings.cache_clear()
    db_module._engine = None


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        r = c.post("/api/organization/setup", json={
            "displayName": "Test Organization",
            "ownerName": "Test Owner",
            "ownerEmail": "owner@example.com",
            "accessMode": "public",
            "marketplaceCreation": "authenticated",
            "provider": {
                "provider": "local",
                "admin": {
                    "email": "admin@example.com",
                    "displayName": "Admin",
                    "password": "admin-pass-1234",
                },
            },
        })
        assert r.status_code == 200
        yield c


# ── Marketplace CRUD ──────────────────────────────────────────────────────────

def test_list_empty(client):
    r = client.get("/api/marketplaces")
    assert r.status_code == 200
    assert r.json() == []


def test_create_marketplace(client):
    r = client.post("/api/marketplaces", json={
        "displayName": "Finance Team",
        "ownerName": "Alice",
        "ownerEmail": "alice@example.com",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "finance-team"
    assert data["displayName"] == "Finance Team"
    assert data["skillCount"] == 0


def test_create_marketplace_409_on_collision(client):
    r = client.post("/api/marketplaces", json={
        "displayName": "Finance Team",  # same slug
        "ownerName": "Bob",
        "ownerEmail": "bob@example.com",
    })
    assert r.status_code == 409


def test_get_marketplace(client):
    r = client.get("/api/marketplaces/finance-team")
    assert r.status_code == 200
    assert r.json()["slug"] == "finance-team"


def test_get_marketplace_404(client):
    r = client.get("/api/marketplaces/does-not-exist")
    assert r.status_code == 404


def test_update_marketplace(client):
    r = client.put("/api/marketplaces/finance-team", json={"displayName": "Finance Team Updated"})
    assert r.status_code == 200
    assert r.json()["displayName"] == "Finance Team Updated"


# ── Skill CRUD ────────────────────────────────────────────────────────────────

def test_create_skill(client):
    r = client.post("/api/marketplaces/finance-team/plugins", json={
        "displayName": "Quarterly Report",
        "description": "Guides quarterly reporting",
    })
    assert r.status_code == 201
    assert r.json()["slug"] == "quarterly-report"

    r = client.post("/api/marketplaces/finance-team/plugins/quarterly-report/skills", json={
        "displayName": "Quarterly Report",
        "description": "Guides quarterly reporting",
        "content": "Follow the quarterly reporting process.",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "quarterly-report"
    assert data["version"] == "1.0.0"
    assert data["lastCommit"] is not None


def test_list_skills(client):
    r = client.get("/api/marketplaces/finance-team/plugins/quarterly-report/skills")
    assert r.status_code == 200
    assert len(r.json()) == 1
    # List endpoint should not include content
    assert "content" not in r.json()[0] or r.json()[0].get("content") is None


def test_get_skill(client):
    r = client.get("/api/marketplaces/finance-team/plugins/quarterly-report/skills/quarterly-report")
    assert r.status_code == 200
    data = r.json()
    assert data["content"] == "Follow the quarterly reporting process."


def test_update_skill_bumps_version(client):
    r = client.put("/api/marketplaces/finance-team/plugins/quarterly-report/skills/quarterly-report", json={
        "content": "Updated content."
    })
    assert r.status_code == 200
    assert r.json()["version"] == "1.0.1"
    assert r.json()["content"] == "Updated content."


def test_marketplace_json_endpoint(client):
    r = client.get("/m/finance-team")
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "finance-team"
    assert len(data["plugins"]) == 1
    plugin = data["plugins"][0]
    assert plugin["source"]["source"] == "url"
    assert plugin["source"]["url"].endswith("/m/finance-team/git/repo.git")
    assert plugin["source"]["path"] == "plugins/quarterly-report"
    assert "\\" not in plugin["source"]["path"]


def test_marketplace_json_alias(client):
    r = client.get("/m/finance-team/marketplace.json")
    assert r.status_code == 200
    assert r.json()["name"] == "finance-team"


def test_delete_skill(client):
    r = client.delete("/api/marketplaces/finance-team/plugins/quarterly-report/skills/quarterly-report")
    assert r.status_code == 204
    r = client.get("/api/marketplaces/finance-team/plugins/quarterly-report/skills/quarterly-report")
    assert r.status_code == 404


def test_marketplace_json_keeps_plugin_after_skill_delete(client):
    r = client.get("/m/finance-team")
    assert r.status_code == 200
    assert [p["name"] for p in r.json()["plugins"]] == ["quarterly-report"]


def test_delete_plugin(client):
    r = client.delete("/api/marketplaces/finance-team/plugins/quarterly-report")
    assert r.status_code == 204
    r = client.get("/m/finance-team")
    assert r.status_code == 200
    assert r.json()["plugins"] == []


def test_top_level_skill_shortcut_removed(client):
    r = client.get("/api/marketplaces/finance-team/skills")
    assert r.status_code == 404


def test_delete_marketplace(client):
    r = client.delete("/api/marketplaces/finance-team")
    assert r.status_code == 204
    r = client.get("/api/marketplaces/finance-team")
    assert r.status_code == 404
    r = client.get("/m/finance-team")
    assert r.status_code == 404


def test_marketplace_isolation(client):
    # Create two marketplaces
    client.post("/api/marketplaces", json={"displayName": "Alpha Team", "ownerName": "A", "ownerEmail": "a@a.com"})
    client.post("/api/marketplaces", json={"displayName": "Beta Team", "ownerName": "B", "ownerEmail": "b@b.com"})
    client.post("/api/marketplaces/alpha-team/plugins", json={"displayName": "Skill A", "description": "d"})
    client.post("/api/marketplaces/beta-team/plugins", json={"displayName": "Skill B", "description": "d"})
    client.post("/api/marketplaces/alpha-team/plugins/skill-a/skills", json={"displayName": "Skill A", "description": "d", "content": "c"})
    client.post("/api/marketplaces/beta-team/plugins/skill-b/skills", json={"displayName": "Skill B", "description": "d", "content": "c"})

    r_a = client.get("/m/alpha-team")
    r_b = client.get("/m/beta-team")
    assert r_a.status_code == 200
    assert r_b.status_code == 200
    # Each marketplace has only its own skill
    a_plugins = [p["name"] for p in r_a.json()["plugins"]]
    b_plugins = [p["name"] for p in r_b.json()["plugins"]]
    assert "skill-a" in a_plugins
    assert "skill-a" not in b_plugins
    assert "skill-b" in b_plugins
    assert "skill-b" not in a_plugins

    # Delete alpha — beta unaffected
    client.delete("/api/marketplaces/alpha-team")
    assert client.get("/m/alpha-team").status_code == 404
    assert client.get("/m/beta-team").status_code == 200


def test_multi_capability_plugin_crud(client):
    r = client.post("/api/marketplaces", json={
        "displayName": "Plugin Team",
        "ownerName": "Plugin Owner",
        "ownerEmail": "plugins@example.com",
    })
    assert r.status_code == 201

    r = client.post("/api/marketplaces/plugin-team/plugins", json={
        "displayName": "Ops Toolkit",
        "description": "Operational helpers",
    })
    assert r.status_code == 201
    assert r.json()["slug"] == "ops-toolkit"

    assert client.post("/api/marketplaces/plugin-team/plugins/ops-toolkit/skills", json={
        "displayName": "Triage",
        "description": "Triage incidents",
        "content": "Follow the incident checklist.",
    }).status_code == 201
    assert client.post("/api/marketplaces/plugin-team/plugins/ops-toolkit/hooks", json={
        "displayName": "Format on edit",
        "event": "PostToolUse",
        "matcher": "Write|Edit",
        "handler": {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/scripts/format.sh", "timeout": 30},
        "unsafeConfirmed": True,
    }).status_code == 201
    assert client.post("/api/marketplaces/plugin-team/plugins/ops-toolkit/agents", json={
        "displayName": "Reviewer",
        "description": "Reviews changes",
        "prompt": "Review the change.",
        "config": {"model": "sonnet", "maxTurns": 5},
    }).status_code == 201
    assert client.post("/api/marketplaces/plugin-team/plugins/ops-toolkit/mcp-servers", json={
        "displayName": "Status API",
        "config": {"type": "http", "url": "https://status.example.com/mcp"},
        "unsafeConfirmed": True,
    }).status_code == 201
    assert client.post("/api/marketplaces/plugin-team/plugins/ops-toolkit/commands", json={
        "displayName": "Deploy",
        "description": "Deploy safely",
        "content": "Deploy with $ARGUMENTS.",
    }).status_code == 201
    assert client.post("/api/marketplaces/plugin-team/plugins/ops-toolkit/monitors", json={
        "displayName": "Error Log",
        "command": "tail -F ./logs/error.log",
        "description": "Application error log",
        "when": "always",
        "unsafeConfirmed": True,
    }).status_code == 201
    assert client.put("/api/marketplaces/plugin-team/plugins/ops-toolkit/settings", json={
        "settings": {"agent": "reviewer"},
    }).status_code == 200

    r = client.get("/api/marketplaces/plugin-team/plugins/ops-toolkit")
    assert r.status_code == 200
    data = r.json()
    assert data["skillCount"] == 1
    assert data["hookCount"] == 1
    assert data["agentCount"] == 1
    assert data["mcpServerCount"] == 1
    assert data["commandCount"] == 1
    assert data["monitorCount"] == 1
    assert data["hasSettings"] is True

    r = client.get("/m/plugin-team")
    assert r.status_code == 200
    plugin = r.json()["plugins"][0]
    assert plugin["name"] == "ops-toolkit"
    assert plugin["source"]["path"] == "plugins/ops-toolkit"

    assert client.delete("/api/marketplaces/plugin-team/plugins/ops-toolkit/hooks/format-on-edit").status_code == 204
    assert client.get("/api/marketplaces/plugin-team/plugins/ops-toolkit").json()["hookCount"] == 0


def test_restricted_mode_filters_marketplaces_and_allows_scoped_read_tokens(client):
    r = client.post("/api/marketplaces", json={
        "displayName": "Private Team",
        "ownerName": "Owner",
        "ownerEmail": "owner@example.com",
    })
    assert r.status_code == 201
    assert client.put("/api/marketplaces/private-team", json={"visibility": "restricted"}).status_code == 200

    token_response = client.post("/api/access-tokens", json={
        "name": "Claude read",
        "marketplaceSlug": "private-team",
    })
    assert token_response.status_code == 201
    token = token_response.json()["token"]

    assert client.put("/api/organization/settings", json={"accessMode": "restricted"}).status_code == 200
    client.cookies.clear()
    assert client.get("/api/marketplaces").json() == []
    assert client.get("/m/private-team").status_code == 401
    assert client.get("/m/private-team", params={"access_token": token}).status_code == 200
    assert client.post("/auth/login/local", json={"email": "admin@example.com", "password": "admin-pass-1234"}).status_code == 200
    visible_slugs = {row["slug"] for row in client.get("/api/marketplaces").json()}
    assert "private-team" in visible_slugs


def test_development_mode_does_not_grant_anonymous_admin(client):
    client.cookies.clear()
    me = client.get("/api/me").json()
    assert me["authenticated"] is False
    assert me["organizationAdmin"] is False
    assert client.put("/api/organization/settings", json={"accessMode": "authenticated"}).status_code == 401
    assert client.post("/auth/login/local", json={"email": "admin@example.com", "password": "admin-pass-1234"}).status_code == 200
    r = client.put("/api/organization/settings", json={"accessMode": "public"})
    assert r.status_code == 200
    assert r.json()["accessMode"] == "public"


def test_organization_settings_update(client):
    r = client.put("/api/organization/settings", json={
        "accessMode": "authenticated",
        "marketplaceCreation": "organization_admin",
    })
    assert r.status_code == 200
    assert r.json()["marketplaceCreation"] == "organization_admin"
    assert client.put("/api/organization/settings", json={"accessMode": "public"}).status_code == 200


def test_auth_provider_config_references_secret_env_without_storing_secret(client, monkeypatch):
    monkeypatch.setenv("SKILLSHELF_GITHUB_CLIENT_SECRET", "super-secret")
    r = client.post("/api/organization/auth-providers", json={
        "slug": "github-test",
        "displayName": "GitHub Test",
        "providerType": "github",
        "clientId": "abc123",
        "clientSecretEnvVar": "SKILLSHELF_GITHUB_CLIENT_SECRET",
        "scopes": "read:user user:email",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["secretConfigured"] is True
    assert "super-secret" not in str(data)

    providers = client.get("/api/organization/auth-providers").json()
    assert any(p["slug"] == "github-test" and p["secretConfigured"] for p in providers)


def test_marketplace_admin_cannot_manage_organization_settings_in_authenticated_mode(client):
    assert client.put("/api/organization/settings", json={
        "accessMode": "authenticated",
        "marketplaceCreation": "authenticated",
    }).status_code == 200
    r = client.post("/api/marketplaces", json={
        "displayName": "Marketplace Admin Only",
        "ownerName": "Market Admin",
        "ownerEmail": "market-admin@example.com",
    })
    assert r.status_code == 201
    r = client.post("/api/organization/users", json={
        "email": "maintainer@example.com",
        "displayName": "Maintainer",
    })
    assert r.status_code == 201
    password = r.json()["temporaryPassword"]
    client.cookies.clear()
    assert client.post("/auth/login/local", json={"email": "maintainer@example.com", "password": password}).status_code == 200
    assert client.post("/auth/change-password", json={"current_password": password, "new_password": "maintainer-pass-1234"}).status_code == 200
    assert client.put(
        "/api/organization/settings",
        json={"accessMode": "restricted"},
    ).status_code == 403
    client.cookies.clear()
    assert client.post("/auth/login/local", json={"email": "admin@example.com", "password": "admin-pass-1234"}).status_code == 200
    assert client.put("/api/organization/settings", json={"accessMode": "public"}).status_code == 200
