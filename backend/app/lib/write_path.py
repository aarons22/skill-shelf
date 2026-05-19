"""
The canonical write path (§9) — shared by all mutating API operations.

Every mutation that touches the git store must go through one of these helpers
so atomicity between SQLite and the git repo is guaranteed.
"""
import posixpath
from typing import Any

from sqlalchemy.engine import Connection

from app.lib import git_store, marketplace_json


def _plugin_json(skill_slug: str) -> str:
    import json
    return json.dumps({
        "name": skill_slug,
        "skills": [f"skills/{skill_slug}/SKILL.md"],
    }, indent=2)


def _skill_md(slug: str, description: str, content: str) -> str:
    return f"---\nname: {slug}\ndescription: {description}\n---\n{content}\n"


def build_skill_files(marketplace_slug: str, skill_slug: str, description: str, content: str) -> dict[str, str]:
    """Return the full set of files a skill contributes to the working tree."""
    base = f"plugins/{skill_slug}"
    return {
        f"{base}/.claude-plugin/plugin.json": _plugin_json(skill_slug),
        f"{base}/skills/{skill_slug}/SKILL.md": _skill_md(skill_slug, description, content),
    }


def remove_skill_files(skill_slug: str) -> dict[str, None]:
    """Return deletion entries for all files belonging to a skill."""
    base = f"plugins/{skill_slug}"
    return {
        f"{base}/.claude-plugin/plugin.json": None,
        f"{base}/skills/{skill_slug}/SKILL.md": None,
    }


def sync_and_commit(
    marketplace_slug: str,
    conn: Connection,
    commit_message: str,
    author_name: str,
    author_email: str,
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
    # Step 5: regenerate marketplace.json (always full rewrite)
    mj = marketplace_json.serialize_marketplace_json(marketplace_slug, conn)
    files: dict[str, str | None] = {".claude-plugin/marketplace.json": mj}

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
