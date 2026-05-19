import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, insert, select, update

from app.db import get_connection, get_transaction
from app.lib.auth import (
    Actor,
    ensure_workspace_settings,
    generate_token,
    get_optional_actor,
    is_workspace_admin,
    record_audit,
    require_marketplace_admin,
    require_workspace_admin,
    token_hash,
)
from app.models import access_tokens, marketplace_role_grants, marketplaces, workspace_settings
from app.schemas import (
    AccessTokenCreate,
    AccessTokenCreatedOut,
    AccessTokenOut,
    CurrentUserOut,
    MarketplaceGrantOut,
    PrincipalGrantIn,
    WorkspaceSettingsOut,
    WorkspaceSettingsUpdate,
)

router = APIRouter(prefix="/api", tags=["access"])


@router.get("/me", response_model=CurrentUserOut)
def me(actor: Actor | None = Depends(get_optional_actor)):
    if actor is None:
        return {"authenticated": False}
    with get_connection() as conn:
        return {
            "authenticated": True,
            "id": actor.user_id,
            "email": actor.email,
            "displayName": actor.display_name,
            "workspaceAdmin": is_workspace_admin(conn, actor),
        }


@router.get("/workspace/settings", response_model=WorkspaceSettingsOut)
def get_workspace_settings():
    with get_transaction() as conn:
        row = ensure_workspace_settings(conn)
        return {"accessMode": row["access_mode"], "marketplaceCreation": row["marketplace_creation"]}


@router.put("/workspace/settings", response_model=WorkspaceSettingsOut)
def update_workspace_settings(body: WorkspaceSettingsUpdate, actor: Actor | None = Depends(get_optional_actor)):
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        current = ensure_workspace_settings(conn)
        values = {}
        if body.accessMode is not None:
            values["access_mode"] = body.accessMode
        if body.marketplaceCreation is not None:
            values["marketplace_creation"] = body.marketplaceCreation
        if values:
            values["updated_at"] = int(time.time())
            conn.execute(update(workspace_settings).where(workspace_settings.c.id == 1).values(**values))
            record_audit(conn, actor, "workspace_settings.update", "workspace", "settings", values)
            current = {**current, **values}
        return {"accessMode": current["access_mode"], "marketplaceCreation": current["marketplace_creation"]}


@router.get("/marketplaces/{slug}/grants", response_model=list[MarketplaceGrantOut])
def list_marketplace_grants(slug: str, actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        _marketplace_exists_or_404(conn, slug)
        require_marketplace_admin(conn, actor, slug)
        rows = conn.execute(
            select(marketplace_role_grants).where(
                marketplace_role_grants.c.marketplace_slug == slug
            ).order_by(
                marketplace_role_grants.c.principal_type,
                marketplace_role_grants.c.principal_id,
                marketplace_role_grants.c.role,
            )
        ).mappings().all()
        return [_grant_out(row) for row in rows]


@router.post("/marketplaces/{slug}/grants", response_model=MarketplaceGrantOut, status_code=201)
def add_marketplace_grant(slug: str, body: PrincipalGrantIn, actor: Actor | None = Depends(get_optional_actor)):
    now = int(time.time())
    with get_transaction() as conn:
        _marketplace_exists_or_404(conn, slug)
        require_marketplace_admin(conn, actor, slug)
        exists = conn.execute(
            select(marketplace_role_grants.c.role).where(
                marketplace_role_grants.c.marketplace_slug == slug,
                marketplace_role_grants.c.principal_type == body.principalType,
                marketplace_role_grants.c.principal_id == body.principalId,
                marketplace_role_grants.c.role == body.role,
            )
        ).one_or_none()
        if exists is None:
            conn.execute(insert(marketplace_role_grants).values(
                marketplace_slug=slug,
                principal_type=body.principalType,
                principal_id=body.principalId,
                role=body.role,
                created_at=now,
            ))
            record_audit(conn, actor, "marketplace_grant.add", "marketplace", slug, body.model_dump())
        row = conn.execute(
            select(marketplace_role_grants).where(
                marketplace_role_grants.c.marketplace_slug == slug,
                marketplace_role_grants.c.principal_type == body.principalType,
                marketplace_role_grants.c.principal_id == body.principalId,
                marketplace_role_grants.c.role == body.role,
            )
        ).mappings().one()
        return _grant_out(row)


@router.delete("/marketplaces/{slug}/grants/{principal_type}/{principal_id}/{role}", status_code=204)
def delete_marketplace_grant(
    slug: str,
    principal_type: str,
    principal_id: int,
    role: str,
    actor: Actor | None = Depends(get_optional_actor),
):
    with get_transaction() as conn:
        _marketplace_exists_or_404(conn, slug)
        require_marketplace_admin(conn, actor, slug)
        conn.execute(
            delete(marketplace_role_grants).where(
                marketplace_role_grants.c.marketplace_slug == slug,
                marketplace_role_grants.c.principal_type == principal_type,
                marketplace_role_grants.c.principal_id == principal_id,
                marketplace_role_grants.c.role == role,
            )
        )
        record_audit(conn, actor, "marketplace_grant.delete", "marketplace", slug, {
            "principalType": principal_type,
            "principalId": principal_id,
            "role": role,
        })


@router.get("/access-tokens", response_model=list[AccessTokenOut])
def list_access_tokens(actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        require_workspace_admin(conn, actor)
        rows = conn.execute(select(access_tokens).order_by(access_tokens.c.created_at.desc())).mappings().all()
        return [_token_out(row) for row in rows]


@router.post("/access-tokens", response_model=AccessTokenCreatedOut, status_code=201)
def create_access_token(body: AccessTokenCreate, actor: Actor | None = Depends(get_optional_actor)):
    now = int(time.time())
    with get_transaction() as conn:
        if body.marketplaceSlug:
            _marketplace_exists_or_404(conn, body.marketplaceSlug)
            require_marketplace_admin(conn, actor, body.marketplaceSlug)
        else:
            require_workspace_admin(conn, actor)
        raw = generate_token()
        conn.execute(insert(access_tokens).values(
            name=body.name,
            token_hash=token_hash(raw),
            scope="marketplace_read",
            marketplace_slug=body.marketplaceSlug,
            created_by_user_id=actor.user_id if actor else None,
            created_at=now,
            expires_at=body.expiresAt,
        ))
        record_audit(conn, actor, "access_token.create", "access_token", body.name, {
            "marketplaceSlug": body.marketplaceSlug,
            "expiresAt": body.expiresAt,
        })
        row = conn.execute(
            select(access_tokens).where(access_tokens.c.token_hash == token_hash(raw))
        ).mappings().one()
        return {**_token_out(row), "token": raw}


@router.delete("/access-tokens/{token_id}", status_code=204)
def revoke_access_token(token_id: int, actor: Actor | None = Depends(get_optional_actor)):
    with get_transaction() as conn:
        token = conn.execute(select(access_tokens).where(access_tokens.c.id == token_id)).mappings().one_or_none()
        if token is None:
            raise HTTPException(status_code=404, detail="Access token not found")
        if token["marketplace_slug"]:
            require_marketplace_admin(conn, actor, token["marketplace_slug"])
        else:
            require_workspace_admin(conn, actor)
        conn.execute(update(access_tokens).where(access_tokens.c.id == token_id).values(revoked_at=int(time.time())))
        record_audit(conn, actor, "access_token.revoke", "access_token", str(token_id), {
            "marketplaceSlug": token["marketplace_slug"],
        })


def _marketplace_exists_or_404(conn, slug: str) -> None:
    exists = conn.execute(select(marketplaces.c.slug).where(marketplaces.c.slug == slug)).one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")


def _grant_out(row) -> dict:
    return {
        "marketplaceSlug": row["marketplace_slug"],
        "principalType": row["principal_type"],
        "principalId": row["principal_id"],
        "role": row["role"],
        "createdAt": row["created_at"],
    }


def _token_out(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "scope": row["scope"],
        "marketplaceSlug": row["marketplace_slug"],
        "expiresAt": row["expires_at"],
        "revokedAt": row["revoked_at"],
        "createdAt": row["created_at"],
    }
