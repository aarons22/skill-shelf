"""Unit tests for the marketplace.json builder.

Uses an in-memory SQLite DB (no filesystem, no git).
"""
import time

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.engine import Connection

from app.lib.marketplace_json import build_codex_marketplace_json, build_marketplace_json
from app.models import metadata, marketplaces, plugins, skills


@pytest.fixture
def conn(monkeypatch):
    """In-memory SQLite connection with schema + a test marketplace."""
    # Override PUBLIC_BASE_URL for deterministic assertions
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://skillshelf.example.com")
    # Reset the settings cache so the env var is picked up
    from app import config as cfg
    cfg.get_settings.cache_clear()

    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    now = int(time.time())
    with engine.connect() as c:
        c.execute(insert(marketplaces).values(
            slug="finance-team",
            display_name="Finance Team",
            owner_name="Alice",
            owner_email="alice@example.com",
            created_at=now,
            updated_at=now,
        ))
        c.commit()
        yield c

    cfg.get_settings.cache_clear()


def test_empty_plugins(conn):
    result = build_marketplace_json("finance-team", conn)
    assert result["name"] == "finance-team"
    assert result["owner"] == {"name": "Alice", "email": "alice@example.com"}
    assert result["plugins"] == []


def test_single_skill(conn):
    now = int(time.time())
    _insert_plugin(conn, "quarterly-report", "Quarterly Report", "Guides quarterly reporting", now)
    conn.execute(insert(skills).values(
        marketplace_slug="finance-team",
        plugin_slug="quarterly-report",
        slug="quarterly-report",
        display_name="Quarterly Report",
        description="Guides quarterly reporting",
        version="1.0.0",
        content="...",
        created_at=now,
        updated_at=now,
    ))
    conn.commit()

    result = build_marketplace_json("finance-team", conn)
    assert len(result["plugins"]) == 1
    plugin = result["plugins"][0]
    assert plugin["name"] == "quarterly-report"
    assert plugin["description"] == "Guides quarterly reporting"
    assert plugin["version"] == "1.0.0"
    assert plugin["source"]["source"] == "url"
    assert plugin["source"]["url"] == "https://skillshelf.example.com/m/finance-team/git/repo.git"
    assert plugin["source"]["path"] == "plugins/quarterly-report"


def test_codex_marketplace_json(conn):
    now = int(time.time())
    _insert_plugin(conn, "quarterly-report", "Quarterly Report", "Guides quarterly reporting", now)
    conn.execute(insert(skills).values(
        marketplace_slug="finance-team",
        plugin_slug="quarterly-report",
        slug="quarterly-report",
        display_name="Quarterly Report",
        description="Guides quarterly reporting",
        version="1.0.0",
        content="...",
        created_at=now,
        updated_at=now,
    ))
    conn.commit()

    result = build_codex_marketplace_json("finance-team", conn)
    assert result["name"] == "finance-team"
    assert result["interface"]["displayName"] == "Finance Team"
    assert len(result["plugins"]) == 1
    plugin = result["plugins"][0]
    assert plugin == {
        "name": "quarterly-report",
        "source": {
            "source": "local",
            "path": "./plugins/quarterly-report",
        },
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Productivity",
    }


def test_source_path_uses_forward_slashes(conn):
    """source.path must use / on all platforms (posixpath, never os.path.join)."""
    now = int(time.time())
    _insert_plugin(conn, "my-skill", "My Skill", "desc", now)
    conn.execute(insert(skills).values(
        marketplace_slug="finance-team",
        plugin_slug="my-skill",
        slug="my-skill",
        display_name="My Skill",
        description="desc",
        version="1.0.0",
        content="...",
        created_at=now,
        updated_at=now,
    ))
    conn.commit()
    result = build_marketplace_json("finance-team", conn)
    path = result["plugins"][0]["source"]["path"]
    assert "\\" not in path, f"Backslash found in source.path: {path!r}"
    assert path == "plugins/my-skill"


def test_multiple_plugins_sorted(conn):
    now = int(time.time())
    for slug, name in [("zzz-last", "ZZZ"), ("aaa-first", "AAA"), ("mmm-middle", "MMM")]:
        _insert_plugin(conn, slug, name, f"desc for {slug}", now)
    conn.commit()
    result = build_marketplace_json("finance-team", conn)
    names = [p["name"] for p in result["plugins"]]
    assert names == sorted(names), "plugins should be sorted by slug"


def test_missing_marketplace_raises(conn):
    with pytest.raises(Exception):
        build_marketplace_json("nonexistent", conn)


def _insert_plugin(conn: Connection, slug: str, display_name: str, description: str, now: int) -> None:
    conn.execute(insert(plugins).values(
        marketplace_slug="finance-team",
        slug=slug,
        display_name=display_name,
        description=description,
        version="1.0.0",
        created_at=now,
        updated_at=now,
    ))
