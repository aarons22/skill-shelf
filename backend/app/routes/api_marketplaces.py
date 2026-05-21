import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, insert, select, update

from app.db import get_connection, get_transaction
from app.lib.auth import (
    Actor,
    DEFAULT_ORGANIZATION_ID,
    MARKETPLACE_ADMIN,
    can_create_marketplace,
    get_optional_actor,
    require_marketplace_admin,
    require_marketplace_read,
    record_audit,
    visible_marketplace_condition,
)
from app.lib import git_store, write_path
from app.lib.slug import make_slug
from app.models import marketplace_role_grants, marketplaces, plugins, skills, users
from app.schemas import MarketplaceCreate, MarketplaceOut, MarketplaceUpdate

router = APIRouter(prefix="/api/marketplaces", tags=["marketplaces"])

RESERVED_MARKETPLACE_SLUGS = {"new"}


def _row_to_out(row, skill_count: int | None = None) -> dict[str, Any]:
    return {
        "slug": row["slug"],
        "displayName": row["display_name"],
        "ownerName": row["owner_display_name"] or "",
        "ownerEmail": row["owner_email"] or "",
        "visibility": row["visibility"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "skillCount": skill_count,
        "pluginCount": None,
    }


def _marketplace_with_owner(conn, where_clause=None):
    """Select marketplaces joined to their owner user."""
    stmt = (
        select(
            marketplaces,
            users.c.display_name.label("owner_display_name"),
            users.c.email.label("owner_email"),
        )
        .select_from(marketplaces.outerjoin(users, marketplaces.c.created_by_user_id == users.c.id))
    )
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    return stmt


@router.get("", response_model=list[MarketplaceOut])
def list_marketplaces(request: Request, actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        condition = visible_marketplace_condition(conn, actor)
        stmt = _marketplace_with_owner(conn, condition).order_by(marketplaces.c.display_name)
        rows = conn.execute(stmt).mappings().all()
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
def get_marketplace(slug: str, request: Request, actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        row = conn.execute(
            _marketplace_with_owner(conn, marketplaces.c.slug == slug)
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Marketplace not found")
        require_marketplace_read(conn, actor, slug)
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
def create_marketplace(body: MarketplaceCreate, request: Request, actor: Actor | None = Depends(get_optional_actor)):
    slug = make_slug(body.displayName)
    now = int(time.time())

    if slug in RESERVED_MARKETPLACE_SLUGS:
        raise HTTPException(status_code=409, detail=f"Slug '{slug}' is reserved")

    # Collision check (outside transaction to avoid locking)
    with get_connection() as conn:
        if not can_create_marketplace(conn, actor):
            if actor is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            raise HTTPException(status_code=403, detail="Marketplace creation is not allowed")
        existing = conn.execute(
            select(marketplaces.c.slug).where(marketplaces.c.slug == slug)
        ).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Slug '{slug}' already exists")

    if actor is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Create git repo before transaction (easier to clean up on failure)
    git_store.create_repo(slug)

    try:
        with get_transaction() as conn:
            conn.execute(insert(marketplaces).values(
                organization_id=DEFAULT_ORGANIZATION_ID,
                slug=slug,
                display_name=body.displayName,
                created_by_user_id=actor.user_id,
                visibility="workspace",
                created_at=now,
                updated_at=now,
            ))
            if actor.user_id is not None:
                conn.execute(insert(marketplace_role_grants).values(
                    organization_id=DEFAULT_ORGANIZATION_ID,
                    marketplace_slug=slug,
                    principal_type="user",
                    principal_id=actor.user_id,
                    role=MARKETPLACE_ADMIN,
                    created_at=now,
                ))
            write_path.sync_and_commit(slug, conn, commit_message="Initialize marketplace")
    except Exception:
        git_store.delete_repo(slug)
        raise

    with get_connection() as conn:
        row = conn.execute(_marketplace_with_owner(conn, marketplaces.c.slug == slug)).mappings().one()
        out = _row_to_out(row, 0)
        out["pluginCount"] = 0
        return out


@router.put("/{slug}", response_model=MarketplaceOut)
def update_marketplace(slug: str, body: MarketplaceUpdate, request: Request, actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        row = conn.execute(
            select(marketplaces).where(marketplaces.c.slug == slug)
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    with get_connection() as conn:
        require_marketplace_admin(conn, actor, slug)

    updates: dict = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.visibility is not None:
        updates["visibility"] = body.visibility

    if not updates:
        with get_connection() as conn:
            skill_count = conn.execute(
                select(func.count()).where(skills.c.marketplace_slug == slug)
            ).scalar()
            plugin_count = conn.execute(
                select(func.count()).where(plugins.c.marketplace_slug == slug)
            ).scalar()
            existing_row = conn.execute(_marketplace_with_owner(conn, marketplaces.c.slug == slug)).mappings().one()
        out = _row_to_out(existing_row, skill_count)
        out["pluginCount"] = plugin_count
        return out

    now = int(time.time())
    updates["updated_at"] = now

    try:
        with get_transaction() as conn:
            conn.execute(update(marketplaces).where(marketplaces.c.slug == slug).values(**updates))
            write_path.sync_and_commit(slug, conn, commit_message="Update marketplace metadata")
    except Exception:
        git_store.reset_working_tree(slug)
        raise

    with get_connection() as conn:
        updated_row = conn.execute(_marketplace_with_owner(conn, marketplaces.c.slug == slug)).mappings().one()
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
def delete_marketplace(slug: str, request: Request, actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        row = conn.execute(
            select(marketplaces.c.slug).where(marketplaces.c.slug == slug)
        ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    with get_connection() as conn:
        require_marketplace_admin(conn, actor, slug)

    with get_transaction() as conn:
        actor = require_marketplace_admin(conn, actor, slug)
        conn.execute(delete(marketplaces).where(marketplaces.c.slug == slug))
        record_audit(conn, actor, "marketplace.delete", "marketplace", slug)

    # delete_repo also evicts the WSGI cache for this slug
    git_store.delete_repo(slug)
