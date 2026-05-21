"""Integration tests for the API routes — uses FastAPI's TestClient (no real server)."""
import os
from urllib.parse import parse_qs, urlparse

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
    r = client.post("/api/marketplaces", json={"displayName": "Finance Team"})
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "finance-team"
    assert data["displayName"] == "Finance Team"
    assert data["skillCount"] == 0


def test_create_marketplace_409_on_collision(client):
    r = client.post("/api/marketplaces", json={"displayName": "Finance Team"})
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
    client.post("/api/marketplaces", json={"displayName": "Alpha Team"})
    client.post("/api/marketplaces", json={"displayName": "Beta Team"})
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
    r = client.post("/api/marketplaces", json={"displayName": "Plugin Team"})
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
    r = client.post("/api/marketplaces", json={"displayName": "Private Team"})
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


def test_restricted_marketplace_requires_grant_even_in_public_mode(client):
    client.cookies.clear()
    assert client.post("/auth/login/local", json={"email": "admin@example.com", "password": "admin-pass-1234"}).status_code == 200
    assert client.put("/api/organization/settings", json={"accessMode": "public"}).status_code == 200

    public_marketplace = client.post("/api/marketplaces", json={"displayName": "Public Visibility Probe"})
    assert public_marketplace.status_code == 201
    restricted_marketplace = client.post("/api/marketplaces", json={"displayName": "Restricted Visibility Probe"})
    assert restricted_marketplace.status_code == 201
    restricted_slug = restricted_marketplace.json()["slug"]
    assert client.put(f"/api/marketplaces/{restricted_slug}", json={"visibility": "restricted"}).status_code == 200

    token_response = client.post("/api/access-tokens", json={
        "name": "Restricted probe read",
        "marketplaceSlug": restricted_slug,
    })
    assert token_response.status_code == 201
    token = token_response.json()["token"]

    outsider = client.post("/api/organization/users", json={
        "email": "public-outsider@example.com",
        "displayName": "Public Outsider",
    })
    assert outsider.status_code == 201
    temporary_password = outsider.json()["temporaryPassword"]

    client.cookies.clear()
    assert client.get(f"/m/{restricted_slug}").status_code == 401
    assert client.get(f"/m/{restricted_slug}", params={"access_token": token}).status_code == 200
    assert client.post("/auth/login/local", json={
        "email": "public-outsider@example.com",
        "password": temporary_password,
    }).status_code == 200
    assert client.post("/auth/change-password", json={
        "current_password": temporary_password,
        "new_password": "public-outsider-pass-1234",
    }).status_code == 200

    visible_slugs = {row["slug"] for row in client.get("/api/marketplaces").json()}
    assert "public-visibility-probe" in visible_slugs
    assert restricted_slug not in visible_slugs
    assert client.get(f"/api/marketplaces/{restricted_slug}").status_code == 403
    assert client.get(f"/m/{restricted_slug}").status_code == 403

    client.cookies.clear()
    assert client.post("/auth/login/local", json={"email": "admin@example.com", "password": "admin-pass-1234"}).status_code == 200
    grant = client.put(f"/api/marketplaces/{restricted_slug}/users/{outsider.json()['id']}/role", json={
        "marketplaceRole": "viewer",
    })
    assert grant.status_code == 200

    client.cookies.clear()
    assert client.post("/auth/login/local", json={
        "email": "public-outsider@example.com",
        "password": "public-outsider-pass-1234",
    }).status_code == 200
    visible_slugs = {row["slug"] for row in client.get("/api/marketplaces").json()}
    assert restricted_slug in visible_slugs
    assert client.get(f"/api/marketplaces/{restricted_slug}").status_code == 200
    assert client.get(f"/m/{restricted_slug}").status_code == 200


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


def test_auth_provider_stores_client_secret_and_never_returns_it(client):
    r = client.post("/api/organization/auth-providers", json={
        "slug": "github-test",
        "displayName": "GitHub Test",
        "providerType": "github",
        "clientId": "abc123",
        "clientSecret": "super-secret",
        "scopes": "garbage-ignored-value",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["secretConfigured"] is True
    assert "super-secret" not in str(data)
    assert "clientSecret" not in data
    assert data["scopes"] == "read:user user:email"

    providers = client.get("/api/organization/auth-providers").json()
    assert any(p["slug"] == "github-test" and p["secretConfigured"] for p in providers)
    github_provider = next(p for p in providers if p["slug"] == "github-test")
    assert "super-secret" not in str(providers)
    assert "clientSecret" not in github_provider
    assert github_provider["callbackUrl"] == "http://testserver/auth/callback/github-test"
    assert github_provider["scopes"] == "read:user user:email"

    public_providers = client.get("/api/auth/providers").json()
    assert [p["slug"] for p in public_providers[:2]] == ["local", "github-test"]
    assert public_providers[0]["kind"] == "credentials"
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["loginConfigured"] is True
    assert me.json()["publicBaseUrl"] == "http://testserver"
    redirect = client.get("/auth/login/github-test", follow_redirects=False)
    assert redirect.status_code == 302
    query = parse_qs(urlparse(redirect.headers["location"]).query)
    assert query["client_id"] == ["abc123"]
    assert query["redirect_uri"] == ["http://testserver/auth/callback/github-test"]

    # Updating without clientSecret preserves the stored secret
    patch = client.put("/api/organization/auth-providers/github-test", json={"displayName": "GitHub Updated"})
    assert patch.status_code == 200
    assert patch.json()["secretConfigured"] is True

    # Clearing clientSecret removes the secret; login then returns 400
    patch2 = client.put("/api/organization/auth-providers/github-test", json={"clientSecret": ""})
    assert patch2.status_code == 200
    assert patch2.json()["secretConfigured"] is False
    assert client.get("/auth/login/github-test", follow_redirects=False).status_code == 400

    # Allowlist with orgs triggers read:org scope
    r2 = client.post("/api/organization/auth-providers", json={
        "slug": "github-orgs",
        "displayName": "GitHub Orgs",
        "providerType": "github",
        "clientId": "xyz",
        "clientSecret": "org-secret",
        "allowlist": {"orgs": ["acme"]},
    })
    assert r2.status_code == 201
    assert r2.json()["scopes"] == "read:user user:email read:org"


def test_organization_user_roles_can_be_viewed_and_changed(client):
    created = client.post("/api/organization/users", json={
        "email": "roles@example.com",
        "displayName": "Roles User",
    })
    assert created.status_code == 201
    user = created.json()
    assert user["organizationRole"] == "viewer"

    promoted = client.put(f"/api/organization/users/{user['id']}/role", json={
        "organizationRole": "organization_admin",
    })
    assert promoted.status_code == 200
    assert promoted.json()["organizationRole"] == "organization_admin"

    demoted = client.put(f"/api/organization/users/{user['id']}/role", json={
        "organizationRole": "viewer",
    })
    assert demoted.status_code == 200
    assert demoted.json()["organizationRole"] == "viewer"

    admin = next(u for u in client.get("/api/organization/users").json() if u["email"] == "admin@example.com")
    last_admin = client.put(f"/api/organization/users/{admin['id']}/role", json={
        "organizationRole": "viewer",
    })
    assert last_admin.status_code == 400


def test_marketplace_admin_can_assign_user_marketplace_roles(client):
    marketplace = client.post("/api/marketplaces", json={"displayName": "Access Team"})
    assert marketplace.status_code == 201
    slug = marketplace.json()["slug"]
    created = client.post("/api/organization/users", json={
        "email": "contributor@example.com",
        "displayName": "Contributor",
    })
    assert created.status_code == 201
    user = created.json()
    users_response = client.get(f"/api/marketplaces/{slug}/users")
    assert users_response.status_code == 200
    users = users_response.json()
    assert all(u["id"] != user["id"] for u in users)
    owner = next(u for u in users if u["email"] == "admin@example.com")
    assert owner["isOwner"] is True
    assert owner["marketplaceRole"] == "marketplace_admin"
    search_response = client.get(f"/api/marketplaces/{slug}/user-search?q=contrib")
    assert search_response.status_code == 200
    listed_user = next(u for u in search_response.json() if u["id"] == user["id"])
    assert listed_user["marketplaceRole"] == "none"
    assert listed_user["isOwner"] is False

    grant = client.put(f"/api/marketplaces/{slug}/users/{user['id']}/role", json={
        "marketplaceRole": "marketplace_maintainer",
    })
    assert grant.status_code == 200
    assert grant.json()["marketplaceRole"] == "marketplace_maintainer"
    users_response = client.get(f"/api/marketplaces/{slug}/users")
    assert any(u["id"] == user["id"] and u["marketplaceRole"] == "marketplace_maintainer" for u in users_response.json())

    client.cookies.clear()
    assert client.post("/auth/login/local", json={
        "email": "contributor@example.com",
        "password": user["temporaryPassword"],
    }).status_code == 200
    assert client.post("/auth/change-password", json={
        "current_password": user["temporaryPassword"],
        "new_password": "contributor-pass-1234",
    }).status_code == 200
    me = client.get("/api/me").json()
    assert slug in me["marketplaceMaintainerSlugs"]
    assert client.post(f"/api/marketplaces/{slug}/plugins", json={
        "displayName": "Maintained Plugin",
        "description": "Created by a maintainer",
    }).status_code == 201
    assert client.get(f"/api/marketplaces/{slug}/users").status_code == 403

    client.cookies.clear()
    assert client.post("/auth/login/local", json={"email": "admin@example.com", "password": "admin-pass-1234"}).status_code == 200
    owner = next(u for u in client.get(f"/api/marketplaces/{slug}/users").json() if u["email"] == "admin@example.com")
    last_admin = client.put(f"/api/marketplaces/{slug}/users/{owner['id']}/role", json={
        "marketplaceRole": "marketplace_maintainer",
    })
    assert last_admin.status_code == 400
    assert "owner" in last_admin.json()["detail"].lower()


def test_marketplace_contributor_can_write_but_not_delete_content(client):
    marketplace = client.post("/api/marketplaces", json={"displayName": "Contributor Team"})
    assert marketplace.status_code == 201
    slug = marketplace.json()["slug"]
    created = client.post("/api/organization/users", json={
        "email": "writer@example.com",
        "displayName": "Writer",
    })
    assert created.status_code == 201
    user = created.json()
    grant = client.put(f"/api/marketplaces/{slug}/users/{user['id']}/role", json={
        "marketplaceRole": "marketplace_contributor",
    })
    assert grant.status_code == 200
    assert grant.json()["marketplaceRole"] == "marketplace_contributor"

    client.cookies.clear()
    assert client.post("/auth/login/local", json={
        "email": "writer@example.com",
        "password": user["temporaryPassword"],
    }).status_code == 200
    assert client.post("/auth/change-password", json={
        "current_password": user["temporaryPassword"],
        "new_password": "writer-pass-1234",
    }).status_code == 200
    me = client.get("/api/me").json()
    assert slug in me["marketplaceContributorSlugs"]

    plugin = client.post(f"/api/marketplaces/{slug}/plugins", json={
        "displayName": "Contributor Plugin",
        "description": "Created by a contributor",
    })
    assert plugin.status_code == 201
    plugin_slug = plugin.json()["slug"]
    assert client.put(f"/api/marketplaces/{slug}/plugins/{plugin_slug}", json={
        "description": "Edited by a contributor",
    }).status_code == 200
    skill = client.post(f"/api/marketplaces/{slug}/plugins/{plugin_slug}/skills", json={
        "displayName": "Contributor Skill",
        "description": "Added by a contributor",
        "content": "Help the team contribute.",
    })
    assert skill.status_code == 201
    assert client.delete(f"/api/marketplaces/{slug}/plugins/{plugin_slug}").status_code == 403
    assert client.delete(f"/api/marketplaces/{slug}/plugins/{plugin_slug}/skills/{skill.json()['slug']}").status_code == 403


def test_marketplace_admin_cannot_manage_organization_settings_in_authenticated_mode(client):
    client.cookies.clear()
    assert client.post("/auth/login/local", json={"email": "admin@example.com", "password": "admin-pass-1234"}).status_code == 200
    assert client.put("/api/organization/settings", json={
        "accessMode": "authenticated",
        "marketplaceCreation": "authenticated",
    }).status_code == 200
    r = client.post("/api/marketplaces", json={"displayName": "Marketplace Admin Only"})
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
