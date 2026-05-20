import os
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, insert, select, update

from app.db import get_connection, get_transaction
from app.lib.auth import (
    Actor,
    DEFAULT_ORGANIZATION_ID,
    ensure_workspace_settings,
    generate_token,
    get_optional_actor,
    is_workspace_admin,
    record_audit,
    require_marketplace_admin,
    require_workspace_admin,
    token_hash,
)
from app.models import access_tokens, auth_providers, marketplace_role_grants, marketplaces, workspace_settings
from app.schemas import (
    AccessTokenCreate,
    AccessTokenCreatedOut,
    AccessTokenOut,
    AuthProviderIn,
    AuthProviderOut,
    AuthProviderUpdate,
    CurrentUserOut,
    MarketplaceGrantOut,
    PrincipalGrantIn,
    WorkspaceSettingsOut,
    WorkspaceSettingsUpdate,
)

router = APIRouter(prefix="/api", tags=["access"])


@router.get("/me", response_model=CurrentUserOut)
def me(actor: Actor | None = Depends(get_optional_actor)):
    login_configured = False
    if actor is None:
        with get_connection() as conn:
            login_configured = conn.execute(
                select(auth_providers.c.id).where(auth_providers.c.enabled == 1)
            ).one_or_none() is not None
        return {"authenticated": False, "loginConfigured": login_configured}
    with get_connection() as conn:
        organization_admin = is_workspace_admin(conn, actor)
        marketplace_admin_slugs = [
            row[0] for row in conn.execute(
                select(marketplace_role_grants.c.marketplace_slug).where(
                    marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                    marketplace_role_grants.c.principal_type == "user",
                    marketplace_role_grants.c.principal_id == actor.user_id,
                    marketplace_role_grants.c.role == "marketplace_admin",
                )
            ).all()
        ] if actor.user_id is not None else []
        login_configured = conn.execute(
            select(auth_providers.c.id).where(auth_providers.c.enabled == 1)
        ).one_or_none() is not None
        return {
            "authenticated": True,
            "id": actor.user_id,
            "email": actor.email,
            "displayName": actor.display_name,
            "workspaceAdmin": organization_admin,
            "organizationAdmin": organization_admin,
            "marketplaceAdminSlugs": marketplace_admin_slugs,
            "provider": "headers" if actor.user_id is not None else None,
            "loginConfigured": login_configured,
        }


@router.get("/organization/settings", response_model=WorkspaceSettingsOut)
def get_organization_settings():
    with get_transaction() as conn:
        row = ensure_workspace_settings(conn)
        return {"accessMode": row["access_mode"], "marketplaceCreation": row["marketplace_creation"]}


@router.get("/workspace/settings", response_model=WorkspaceSettingsOut)
def get_workspace_settings_compat():
    return get_organization_settings()


@router.put("/organization/settings", response_model=WorkspaceSettingsOut)
def update_organization_settings(body: WorkspaceSettingsUpdate, actor: Actor | None = Depends(get_optional_actor)):
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        current = ensure_workspace_settings(conn)
        values = {}
        if body.accessMode is not None:
            values["access_mode"] = body.accessMode
        if body.marketplaceCreation is not None:
            values["marketplace_creation"] = "organization_admin" if body.marketplaceCreation == "workspace_admin" else body.marketplaceCreation
        if values:
            values["updated_at"] = int(time.time())
            conn.execute(update(workspace_settings).where(workspace_settings.c.id == 1).values(**values))
            record_audit(conn, actor, "workspace_settings.update", "workspace", "settings", values)
            current = {**current, **values}
        return {"accessMode": current["access_mode"], "marketplaceCreation": current["marketplace_creation"]}


@router.put("/workspace/settings", response_model=WorkspaceSettingsOut)
def update_workspace_settings_compat(body: WorkspaceSettingsUpdate, actor: Actor | None = Depends(get_optional_actor)):
    return update_organization_settings(body, actor)


@router.get("/organization/auth-providers", response_model=list[AuthProviderOut])
def list_auth_providers(actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        require_workspace_admin(conn, actor)
        rows = conn.execute(
            select(auth_providers).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID
            ).order_by(auth_providers.c.display_name)
        ).mappings().all()
        return [_provider_out(row) for row in rows]


@router.post("/organization/auth-providers", response_model=AuthProviderOut, status_code=201)
def create_auth_provider(body: AuthProviderIn, actor: Actor | None = Depends(get_optional_actor)):
    now = int(time.time())
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        exists = conn.execute(
            select(auth_providers.c.id).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.slug == body.slug,
            )
        ).one_or_none()
        if exists is not None:
            raise HTTPException(status_code=409, detail="Auth provider slug already exists")
        values = _provider_values(body.model_dump(), now)
        values["organization_id"] = DEFAULT_ORGANIZATION_ID
        values["created_at"] = now
        conn.execute(insert(auth_providers).values(**values))
        record_audit(conn, actor, "auth_provider.create", "auth_provider", body.slug, {"providerType": body.providerType})
        row = conn.execute(
            select(auth_providers).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.slug == body.slug,
            )
        ).mappings().one()
        return _provider_out(row)


@router.put("/organization/auth-providers/{provider_slug}", response_model=AuthProviderOut)
def update_auth_provider(provider_slug: str, body: AuthProviderUpdate, actor: Actor | None = Depends(get_optional_actor)):
    now = int(time.time())
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        row = conn.execute(
            select(auth_providers).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.slug == provider_slug,
            )
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Auth provider not found")
        updates = _provider_values(body.model_dump(exclude_unset=True), now)
        if updates:
            conn.execute(update(auth_providers).where(auth_providers.c.id == row["id"]).values(**updates))
            record_audit(conn, actor, "auth_provider.update", "auth_provider", provider_slug, {"fields": sorted(updates)})
        row = conn.execute(select(auth_providers).where(auth_providers.c.id == row["id"])).mappings().one()
        return _provider_out(row)


@router.delete("/organization/auth-providers/{provider_slug}", status_code=204)
def delete_auth_provider(provider_slug: str, actor: Actor | None = Depends(get_optional_actor)):
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        conn.execute(delete(auth_providers).where(
            auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
            auth_providers.c.slug == provider_slug,
        ))
        record_audit(conn, actor, "auth_provider.delete", "auth_provider", provider_slug)


@router.get("/marketplaces/{slug}/grants", response_model=list[MarketplaceGrantOut])
def list_marketplace_grants(slug: str, actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        _marketplace_exists_or_404(conn, slug)
        require_marketplace_admin(conn, actor, slug)
        rows = conn.execute(
            select(marketplace_role_grants).where(
                marketplace_role_grants.c.marketplace_slug == slug,
                marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
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
                marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                marketplace_role_grants.c.principal_type == body.principalType,
                marketplace_role_grants.c.principal_id == body.principalId,
                marketplace_role_grants.c.role == body.role,
            )
        ).one_or_none()
        if exists is None:
            conn.execute(insert(marketplace_role_grants).values(
                organization_id=DEFAULT_ORGANIZATION_ID,
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
                marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
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
                marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
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
        rows = conn.execute(
            select(access_tokens).where(
                access_tokens.c.organization_id == DEFAULT_ORGANIZATION_ID
            ).order_by(access_tokens.c.created_at.desc())
        ).mappings().all()
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
            organization_id=DEFAULT_ORGANIZATION_ID,
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


def _provider_values(raw: dict, now: int) -> dict:
    mapping = {
        "slug": "slug",
        "displayName": "display_name",
        "providerType": "provider_type",
        "enabled": "enabled",
        "clientId": "client_id",
        "clientSecretEnvVar": "client_secret_env_var",
        "issuerUrl": "issuer_url",
        "authorizationUrl": "authorization_url",
        "tokenUrl": "token_url",
        "userinfoUrl": "userinfo_url",
        "scopes": "scopes",
        "groupClaim": "group_claim",
        "allowedOrgs": "allowed_orgs",
    }
    values = {column: raw[key] for key, column in mapping.items() if key in raw}
    if "enabled" in values:
        values["enabled"] = 1 if values["enabled"] else 0
    if values:
        values["updated_at"] = now
    return values


def _provider_out(row) -> dict:
    secret_env = row["client_secret_env_var"] or ""
    return {
        "id": row["id"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "providerType": row["provider_type"],
        "enabled": bool(row["enabled"]),
        "clientId": row["client_id"],
        "clientSecretEnvVar": secret_env,
        "secretConfigured": bool(secret_env and os.getenv(secret_env)),
        "issuerUrl": row["issuer_url"],
        "authorizationUrl": row["authorization_url"],
        "tokenUrl": row["token_url"],
        "userinfoUrl": row["userinfo_url"],
        "scopes": row["scopes"],
        "groupClaim": row["group_claim"],
        "allowedOrgs": row["allowed_orgs"],
        "loginUrl": f"/auth/login/{row['slug']}",
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
