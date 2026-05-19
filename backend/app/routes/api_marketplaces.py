import time
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, func, insert, select, update

from app.db import get_connection, get_transaction
from app.lib import git_store, write_path
from app.lib.slug import make_slug
from app.models import marketplaces, plugins, skills
from app.schemas import MarketplaceCreate, MarketplaceOut, MarketplaceUpdate

router = APIRouter(prefix="/api/marketplaces", tags=["marketplaces"])


def _row_to_out(row, skill_count: int | None = None) -> dict[str, Any]:
    return {
        "slug": row["slug"],
        "displayName": row["display_name"],
        "ownerName": row["owner_name"],
        "ownerEmail": row["owner_email"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "skillCount": skill_count,
        "pluginCount": None,
    }


@router.get("", response_model=list[MarketplaceOut])
def list_marketplaces():
    with get_connection() as conn:
        rows = conn.execute(select(marketplaces).order_by(marketplaces.c.display_name)).mappings().all()
        result = []
        for row in rows:
            skill_count = conn.execute(
                select(func.count()).where(skills.c.marketplace_slug == row["slug"])
            ).scalar()
            plugin_count = conn.execute(
                select(func.count()).where(plugins.c.marketplace_slug == row["slug"])
            ).scalar()
            out = _row_to_out(row, skill_count)
            out["pluginCount"] = plugin_count
            result.append(out)
        return result


@router.get("/{slug}", response_model=MarketplaceOut)
def get_marketplace(slug: str):
    with get_connection() as conn:
        row = conn.execute(
            select(marketplaces).where(marketplaces.c.slug == slug)
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Marketplace not found")
        skill_count = conn.execute(
            select(func.count()).where(skills.c.marketplace_slug == slug)
        ).scalar()
        plugin_count = conn.execute(
            select(func.count()).where(plugins.c.marketplace_slug == slug)
        ).scalar()
        out = _row_to_out(row, skill_count)
        out["pluginCount"] = plugin_count
        return out


@router.post("", response_model=MarketplaceOut, status_code=201)
def create_marketplace(body: MarketplaceCreate):
    slug = make_slug(body.displayName)
    now = int(time.time())

    # Collision check (outside transaction to avoid locking)
    with get_connection() as conn:
        existing = conn.execute(
            select(marketplaces.c.slug).where(marketplaces.c.slug == slug)
        ).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Slug '{slug}' already exists")

    # Create git repo before transaction (easier to clean up on failure)
    git_store.create_repo(slug)

    try:
        with get_transaction() as conn:
            conn.execute(insert(marketplaces).values(
                slug=slug,
                display_name=body.displayName,
                owner_name=body.ownerName,
                owner_email=body.ownerEmail,
                created_at=now,
                updated_at=now,
            ))
            write_path.sync_and_commit(
                slug, conn,
                commit_message="Initialize marketplace",
                author_name=body.ownerName,
                author_email=body.ownerEmail,
            )
    except Exception:
        git_store.delete_repo(slug)
        raise

    with get_connection() as conn:
        row = conn.execute(
            select(marketplaces).where(marketplaces.c.slug == slug)
        ).mappings().one()
        out = _row_to_out(row, 0)
        out["pluginCount"] = 0
        return out


@router.put("/{slug}", response_model=MarketplaceOut)
def update_marketplace(slug: str, body: MarketplaceUpdate):
    with get_connection() as conn:
        row = conn.execute(
            select(marketplaces).where(marketplaces.c.slug == slug)
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")

    updates: dict = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.ownerName is not None:
        updates["owner_name"] = body.ownerName
    if body.ownerEmail is not None:
        updates["owner_email"] = body.ownerEmail

    if not updates:
        with get_connection() as conn:
            skill_count = conn.execute(
                select(func.count()).where(skills.c.marketplace_slug == slug)
            ).scalar()
            plugin_count = conn.execute(
                select(func.count()).where(plugins.c.marketplace_slug == slug)
            ).scalar()
        out = _row_to_out(row, skill_count)
        out["pluginCount"] = plugin_count
        return out

    now = int(time.time())
    updates["updated_at"] = now

    try:
        with get_transaction() as conn:
            conn.execute(update(marketplaces).where(marketplaces.c.slug == slug).values(**updates))
            new_row = conn.execute(
                select(marketplaces).where(marketplaces.c.slug == slug)
            ).mappings().one()
            write_path.sync_and_commit(
                slug, conn,
                commit_message="Update marketplace metadata",
                author_name=new_row["owner_name"],
                author_email=new_row["owner_email"],
            )
    except Exception:
        git_store.reset_working_tree(slug)
        raise

    with get_connection() as conn:
        updated_row = conn.execute(
            select(marketplaces).where(marketplaces.c.slug == slug)
        ).mappings().one()
        skill_count = conn.execute(
            select(func.count()).where(skills.c.marketplace_slug == slug)
        ).scalar()
        plugin_count = conn.execute(
            select(func.count()).where(plugins.c.marketplace_slug == slug)
        ).scalar()
    out = _row_to_out(updated_row, skill_count)
    out["pluginCount"] = plugin_count
    return out


@router.delete("/{slug}", status_code=204)
def delete_marketplace(slug: str):
    with get_connection() as conn:
        row = conn.execute(
            select(marketplaces.c.slug).where(marketplaces.c.slug == slug)
        ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")

    with get_transaction() as conn:
        conn.execute(delete(marketplaces).where(marketplaces.c.slug == slug))

    # delete_repo also evicts the WSGI cache for this slug
    git_store.delete_repo(slug)
