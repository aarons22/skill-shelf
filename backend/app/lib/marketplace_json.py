"""
Builds the marketplace.json payload from SQLite state.

The returned dict matches the §7 contract exactly:
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
from app.models import marketplaces, skills


def build_marketplace_json(slug: str, conn: Connection) -> dict[str, Any]:
    row = conn.execute(
        select(
            marketplaces.c.slug,
            marketplaces.c.display_name,
            marketplaces.c.owner_name,
            marketplaces.c.owner_email,
        ).where(marketplaces.c.slug == slug)
    ).mappings().one_or_none()

    if row is None:
        raise KeyError(f"Marketplace {slug!r} not found")

    skill_rows = conn.execute(
        select(
            skills.c.slug,
            skills.c.description,
            skills.c.version,
        ).where(skills.c.marketplace_slug == slug)
        .order_by(skills.c.slug)
    ).mappings().all()

    base_url = get_settings().public_base_url.rstrip("/")
    git_url = f"{base_url}/m/{slug}/git/repo.git"

    plugins = [
        {
            "name": skill["slug"],
            "description": skill["description"],
            "version": skill["version"],
            "source": {
                "source": "url",
                "url": git_url,
                # posixpath.join — always forward slashes regardless of OS
                "path": posixpath.join("plugins", skill["slug"]),
            },
        }
        for skill in skill_rows
    ]

    return {
        "name": slug,
        "owner": {
            "name": row["owner_name"],
            "email": row["owner_email"],
        },
        "plugins": plugins,
    }


def serialize_marketplace_json(slug: str, conn: Connection) -> str:
    """Return the marketplace.json as a JSON string for writing to disk."""
    import json
    return json.dumps(build_marketplace_json(slug, conn), indent=2)
