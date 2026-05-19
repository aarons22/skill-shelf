import time
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, insert, select, update

from app.db import get_connection, get_transaction
from app.lib import git_store, write_path
from app.lib.slug import make_slug
from app.models import marketplaces, skills
from app.schemas import SkillCreate, SkillOut, SkillUpdate

router = APIRouter(prefix="/api/marketplaces/{marketplace_slug}/skills", tags=["skills"])


def _row_to_out(row, include_content: bool = True) -> dict[str, Any]:
    out = {
        "marketplaceSlug": row["marketplace_slug"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "description": row["description"],
        "version": row["version"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "lastCommit": row["last_commit"],
    }
    if include_content:
        out["content"] = row["content"]
    return out


def _bump_version(version: str) -> str:
    parts = version.split(".")
    if len(parts) == 3:
        parts[-1] = str(int(parts[-1]) + 1)
    return ".".join(parts)


def _get_marketplace_or_404(conn, slug: str):
    row = conn.execute(
        select(marketplaces).where(marketplaces.c.slug == slug)
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")
    return row


@router.get("", response_model=list[SkillOut])
def list_skills(marketplace_slug: str):
    with get_connection() as conn:
        _get_marketplace_or_404(conn, marketplace_slug)
        rows = conn.execute(
            select(skills).where(skills.c.marketplace_slug == marketplace_slug)
            .order_by(skills.c.slug)
        ).mappings().all()
        return [_row_to_out(r, include_content=False) for r in rows]


@router.get("/{skill_slug}", response_model=SkillOut)
def get_skill(marketplace_slug: str, skill_slug: str):
    with get_connection() as conn:
        _get_marketplace_or_404(conn, marketplace_slug)
        row = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Skill not found")
        return _row_to_out(row)


@router.post("", response_model=SkillOut, status_code=201)
def create_skill(marketplace_slug: str, body: SkillCreate):
    skill_slug = make_slug(body.displayName)
    now = int(time.time())

    with get_connection() as conn:
        mkt_row = _get_marketplace_or_404(conn, marketplace_slug)
        existing = conn.execute(
            select(skills.c.slug).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.slug == skill_slug,
            )
        ).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Skill slug '{skill_slug}' already exists")

    try:
        with get_transaction() as conn:
            conn.execute(insert(skills).values(
                marketplace_slug=marketplace_slug,
                slug=skill_slug,
                display_name=body.displayName,
                description=body.description,
                version="1.0.0",
                content=body.content,
                created_at=now,
                updated_at=now,
            ))
            extra = write_path.build_skill_files(marketplace_slug, skill_slug, body.description, body.content)
            sha = write_path.sync_and_commit(
                marketplace_slug, conn,
                commit_message=f"Add skill: {skill_slug}",
                author_name=mkt_row["owner_name"],
                author_email=mkt_row["owner_email"],
                extra_files=extra,
            )
            conn.execute(
                update(skills).where(
                    skills.c.marketplace_slug == marketplace_slug,
                    skills.c.slug == skill_slug,
                ).values(last_commit=sha)
            )
    except Exception:
        git_store.reset_working_tree(marketplace_slug)
        raise

    with get_connection() as conn:
        row = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one()
    return _row_to_out(row)


@router.put("/{skill_slug}", response_model=SkillOut)
def update_skill(marketplace_slug: str, skill_slug: str, body: SkillUpdate):
    with get_connection() as conn:
        mkt_row = _get_marketplace_or_404(conn, marketplace_slug)
        skill_row = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one_or_none()
    if skill_row is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    updates: dict = {}
    if body.displayName is not None:
        updates["display_name"] = body.displayName
    if body.description is not None:
        updates["description"] = body.description
    if body.content is not None:
        updates["content"] = body.content

    if not updates:
        return _row_to_out(skill_row)

    now = int(time.time())
    updates["updated_at"] = now
    updates["version"] = _bump_version(skill_row["version"])

    try:
        with get_transaction() as conn:
            conn.execute(
                update(skills).where(
                    skills.c.marketplace_slug == marketplace_slug,
                    skills.c.slug == skill_slug,
                ).values(**updates)
            )
            new_skill = conn.execute(
                select(skills).where(
                    skills.c.marketplace_slug == marketplace_slug,
                    skills.c.slug == skill_slug,
                )
            ).mappings().one()
            extra = write_path.build_skill_files(
                marketplace_slug, skill_slug,
                new_skill["description"],
                new_skill["content"],
            )
            sha = write_path.sync_and_commit(
                marketplace_slug, conn,
                commit_message=f"Update skill: {skill_slug}",
                author_name=mkt_row["owner_name"],
                author_email=mkt_row["owner_email"],
                extra_files=extra,
            )
            conn.execute(
                update(skills).where(
                    skills.c.marketplace_slug == marketplace_slug,
                    skills.c.slug == skill_slug,
                ).values(last_commit=sha)
            )
    except Exception:
        git_store.reset_working_tree(marketplace_slug)
        raise

    with get_connection() as conn:
        row = conn.execute(
            select(skills).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.slug == skill_slug,
            )
        ).mappings().one()
    return _row_to_out(row)


@router.delete("/{skill_slug}", status_code=204)
def delete_skill(marketplace_slug: str, skill_slug: str):
    with get_connection() as conn:
        mkt_row = _get_marketplace_or_404(conn, marketplace_slug)
        existing = conn.execute(
            select(skills.c.slug).where(
                skills.c.marketplace_slug == marketplace_slug,
                skills.c.slug == skill_slug,
            )
        ).one_or_none()
    if existing is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    try:
        with get_transaction() as conn:
            conn.execute(
                delete(skills).where(
                    skills.c.marketplace_slug == marketplace_slug,
                    skills.c.slug == skill_slug,
                )
            )
            extra = write_path.remove_skill_files(skill_slug)
            write_path.sync_and_commit(
                marketplace_slug, conn,
                commit_message=f"Delete skill: {skill_slug}",
                author_name=mkt_row["owner_name"],
                author_email=mkt_row["owner_email"],
                extra_files=extra,
            )
    except Exception:
        git_store.reset_working_tree(marketplace_slug)
        raise
