"""
Builds marketplace payloads from SQLite state.

The Claude marketplace dict matches the §7 contract exactly:
{
  "name": "<slug>",
  "owner": {"name": "...", "email": "..."},
  "plugins": [
    {
      "name": "<skill-slug>",
      "description": "...",
      "version": "...",
      "source": {
        "source": "url",
        "url": "<PUBLIC_BASE_URL>/m/<slug>/git/repo.git",
        "path": "plugins/<skill-slug>"
      }
    }
  ]
}

source.path ALWAYS uses forward slashes — posixpath.join, never os.path.join.
"""
import posixpath
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.models import marketplaces, plugins, skills, users


def _marketplace_owner(slug: str, conn: Connection) -> tuple[str, str]:
    """Return (display_name, email) for the marketplace owner, falling back to empty strings."""
    row = conn.execute(
        select(users.c.display_name, users.c.email)
        .select_from(
            marketplaces.outerjoin(users, marketplaces.c.created_by_user_id == users.c.id)
        )
        .where(marketplaces.c.slug == slug)
    ).mappings().one_or_none()
    if row and row["display_name"]:
        return row["display_name"], row["email"] or ""
    return "", ""


def build_marketplace_json(slug: str, conn: Connection) -> dict[str, Any]:
    row = conn.execute(
        select(marketplaces.c.slug, marketplaces.c.display_name).where(marketplaces.c.slug == slug)
    ).mappings().one_or_none()

    if row is None:
        raise KeyError(f"Marketplace {slug!r} not found")

    owner_name, owner_email = _marketplace_owner(slug, conn)
    plugin_rows = _plugin_rows(slug, conn)
    base_url = get_settings().public_base_url.rstrip("/")
    git_url = f"{base_url}/m/{slug}/git/repo.git"

    plugins = [
        {
            "name": plugin["slug"],
            "description": plugin["description"],
            "version": plugin["version"],
            "source": {
                "source": "url",
                "url": git_url,
                # posixpath.join — always forward slashes regardless of OS
                "path": posixpath.join("plugins", plugin["slug"]),
            },
        }
        for plugin in plugin_rows
    ]

    return {
        "name": slug,
        "owner": {
            "name": owner_name,
            "email": owner_email,
        },
        "plugins": plugins,
    }


def build_codex_marketplace_json(slug: str, conn: Connection) -> dict[str, Any]:
    row = _marketplace_row(slug, conn)
    plugin_rows = _plugin_rows_with_skills(slug, conn)

    return {
        "name": slug,
        "interface": {
            "displayName": row["display_name"],
        },
        "plugins": [
            {
                "name": plugin["slug"],
                "source": {
                    "source": "local",
                    "path": f"./{posixpath.join('plugins', plugin['slug'])}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
            for plugin in plugin_rows
        ],
    }


def _marketplace_row(slug: str, conn: Connection):
    row = conn.execute(
        select(marketplaces.c.slug, marketplaces.c.display_name).where(marketplaces.c.slug == slug)
    ).mappings().one_or_none()

    if row is None:
        raise KeyError(f"Marketplace {slug!r} not found")
    return row


def _skill_rows(slug: str, conn: Connection):
    return conn.execute(
        select(
            skills.c.slug,
            skills.c.description,
            skills.c.version,
        ).where(skills.c.marketplace_slug == slug)
        .order_by(skills.c.slug)
    ).mappings().all()


def _plugin_rows(slug: str, conn: Connection):
    return conn.execute(
        select(
            plugins.c.slug,
            plugins.c.description,
            plugins.c.version,
        ).where(plugins.c.marketplace_slug == slug)
        .order_by(plugins.c.slug)
    ).mappings().all()


def _plugin_rows_with_skills(slug: str, conn: Connection):
    return conn.execute(
        select(
            plugins.c.slug,
            plugins.c.description,
            plugins.c.version,
        )
        .select_from(
            plugins.join(
                skills,
                (skills.c.marketplace_slug == plugins.c.marketplace_slug)
                & (skills.c.plugin_slug == plugins.c.slug),
            )
        )
        .where(plugins.c.marketplace_slug == slug)
        .group_by(plugins.c.slug, plugins.c.description, plugins.c.version)
        .order_by(plugins.c.slug)
    ).mappings().all()


def build_copilot_marketplace_json(slug: str, conn: Connection) -> dict[str, Any]:
    row = _marketplace_row(slug, conn)
    owner_name, owner_email = _marketplace_owner(slug, conn)
    plugin_rows = _plugin_rows(slug, conn)

    return {
        "name": slug,
        "owner": {
            "name": owner_name,
            "email": owner_email,
        },
        "metadata": {
            "description": row["display_name"],
            "version": "1.0.0",
        },
        "plugins": [
            {
                "name": p["slug"],
                "description": p["description"],
                "version": p["version"],
                "source": f"./plugins/{p['slug']}",
            }
            for p in plugin_rows
        ],
    }


def serialize_marketplace_json(slug: str, conn: Connection) -> str:
    """Return the Claude marketplace.json as a JSON string for writing to disk."""
    import json
    return json.dumps(build_marketplace_json(slug, conn), indent=2)


def serialize_codex_marketplace_json(slug: str, conn: Connection) -> str:
    """Return the Codex marketplace.json as a JSON string for writing to disk."""
    import json
    return json.dumps(build_codex_marketplace_json(slug, conn), indent=2)


def serialize_copilot_marketplace_json(slug: str, conn: Connection) -> str:
    """Return the Copilot marketplace.json as a JSON string for writing to disk."""
    import json
    return json.dumps(build_copilot_marketplace_json(slug, conn), indent=2)
