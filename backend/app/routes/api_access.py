import os
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, insert, select, update

from app.config import get_settings
from app.db import get_connection, get_transaction
from app.lib.auth import (
    Actor,
    DEFAULT_ORGANIZATION_ID,
    ensure_organization_settings,
    generate_token,
    get_optional_actor,
    is_workspace_admin,
    now_ts,
    record_audit,
    require_marketplace_admin,
    require_workspace_admin,
    token_hash,
    upsert_user,
)
from app.lib.local_accounts import generate_temp_password, hash_password
from app.lib.setup_state import is_required
from app.models import access_tokens, auth_providers, local_account_credentials, marketplace_role_grants, marketplaces, organization_role_grants, organization_settings, users
from app.schemas import (
    AccessTokenCreate,
    AccessTokenCreatedOut,
    AccessTokenOut,
    AuthProviderIn,
    AuthProviderOut,
    AuthProviderUpdate,
    CurrentUserOut,
    MarketplaceGrantOut,
    MarketplaceUserOut,
    MarketplaceUserRoleUpdate,
    OrganizationUserCreate,
    OrganizationUserCreatedOut,
    OrganizationUserOut,
    OrganizationUserRoleUpdate,
    PrincipalGrantIn,
    WorkspaceSettingsOut,
    WorkspaceSettingsUpdate,
)

router = APIRouter(prefix="/api", tags=["access"])


@router.get("/me", response_model=CurrentUserOut)
def me(actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        settings = ensure_organization_settings(conn)
        required = is_required(conn)
        public_base_url = get_settings().public_base_url.rstrip("/")
        login_configured = conn.execute(
            select(auth_providers.c.id).where(auth_providers.c.enabled == 1).limit(1)
        ).first() is not None
        if actor is None:
            return {
                "authenticated": False,
                "workspaceAdmin": False,
                "organizationAdmin": False,
                "loginConfigured": login_configured,
                "bootstrapRequired": required,
                "bootstrapCompleted": not required,
                "accessMode": settings["access_mode"],
                "marketplaceCreation": settings["marketplace_creation"],
                "publicBaseUrl": public_base_url,
            }
        organization_admin = is_workspace_admin(conn, actor)
        credential = conn.execute(
            select(local_account_credentials.c.must_change_password).where(
                local_account_credentials.c.user_id == actor.user_id
            )
        ).one_or_none()
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
        marketplace_maintainer_slugs = [
            row[0] for row in conn.execute(
                select(marketplace_role_grants.c.marketplace_slug).where(
                    marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                    marketplace_role_grants.c.principal_type == "user",
                    marketplace_role_grants.c.principal_id == actor.user_id,
                    marketplace_role_grants.c.role == "marketplace_maintainer",
                )
            ).all()
        ] if actor.user_id is not None else []
        user_projection = {"id": actor.user_id, "email": actor.email, "displayName": actor.display_name, "provider": None}
        return {
            "authenticated": True,
            "id": actor.user_id,
            "email": actor.email,
            "displayName": actor.display_name,
            "user": user_projection,
            "workspaceAdmin": organization_admin,
            "organizationAdmin": organization_admin,
            "marketplaceAdminSlugs": marketplace_admin_slugs,
            "marketplaceMaintainerSlugs": marketplace_maintainer_slugs,
            "provider": None,
            "loginConfigured": login_configured,
            "bootstrapRequired": required,
            "bootstrapCompleted": not required,
            "mustChangePassword": bool(credential and credential[0]),
            "accessMode": settings["access_mode"],
            "marketplaceCreation": settings["marketplace_creation"],
            "publicBaseUrl": public_base_url,
        }


@router.get("/organization/settings", response_model=WorkspaceSettingsOut)
def get_organization_settings():
    with get_transaction() as conn:
        row = ensure_organization_settings(conn)
        return {"accessMode": row["access_mode"], "marketplaceCreation": row["marketplace_creation"]}


@router.put("/organization/settings", response_model=WorkspaceSettingsOut)
def update_organization_settings(body: WorkspaceSettingsUpdate, actor: Actor | None = Depends(get_optional_actor)):
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        current = ensure_organization_settings(conn)
        values = {}
        if body.accessMode is not None:
            values["access_mode"] = body.accessMode
        if body.marketplaceCreation is not None:
            values["marketplace_creation"] = body.marketplaceCreation
        if values:
            values["updated_at"] = int(time.time())
            conn.execute(update(organization_settings).where(organization_settings.c.id == 1).values(**values))
            record_audit(conn, actor, "organization_settings.update", "workspace", "settings", values)
            current = {**current, **values}
        return {"accessMode": current["access_mode"], "marketplaceCreation": current["marketplace_creation"]}


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


@router.get("/marketplaces/{slug}/users", response_model=list[MarketplaceUserOut])
def list_marketplace_users(slug: str, actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        _marketplace_exists_or_404(conn, slug)
        require_marketplace_admin(conn, actor, slug)
        rows = conn.execute(
            select(users).where(users.c.organization_id == DEFAULT_ORGANIZATION_ID).order_by(users.c.email)
        ).mappings().all()
        return [_marketplace_user_out(conn, slug, row) for row in rows]


@router.put("/marketplaces/{slug}/users/{user_id}/role", response_model=MarketplaceUserOut)
def update_marketplace_user_role(
    slug: str,
    user_id: int,
    body: MarketplaceUserRoleUpdate,
    actor: Actor | None = Depends(get_optional_actor),
):
    with get_transaction() as conn:
        _marketplace_exists_or_404(conn, slug)
        require_marketplace_admin(conn, actor, slug)
        row = conn.execute(select(users).where(
            users.c.organization_id == DEFAULT_ORGANIZATION_ID,
            users.c.id == user_id,
        )).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        current_role = _marketplace_role_for_user(conn, slug, user_id)
        if current_role == body.marketplaceRole:
            return _marketplace_user_out(conn, slug, row)
        if current_role == "marketplace_admin" and body.marketplaceRole != "marketplace_admin":
            admin_count = conn.execute(
                select(marketplace_role_grants.c.principal_id).where(
                    marketplace_role_grants.c.marketplace_slug == slug,
                    marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                    marketplace_role_grants.c.principal_type == "user",
                    marketplace_role_grants.c.role == "marketplace_admin",
                )
            ).all()
            if len(admin_count) <= 1:
                raise HTTPException(status_code=400, detail="At least one marketplace admin is required")
        conn.execute(delete(marketplace_role_grants).where(
            marketplace_role_grants.c.marketplace_slug == slug,
            marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            marketplace_role_grants.c.principal_type == "user",
            marketplace_role_grants.c.principal_id == user_id,
            marketplace_role_grants.c.role.in_(["viewer", "marketplace_maintainer", "marketplace_admin"]),
        ))
        if body.marketplaceRole != "none":
            conn.execute(insert(marketplace_role_grants).values(
                organization_id=DEFAULT_ORGANIZATION_ID,
                marketplace_slug=slug,
                principal_type="user",
                principal_id=user_id,
                role=body.marketplaceRole,
                created_at=now_ts(),
            ))
        record_audit(conn, actor, "marketplace_user.role_update", "marketplace", slug, {
            "userId": user_id,
            "marketplaceRole": body.marketplaceRole,
        })
        row = conn.execute(select(users).where(users.c.id == user_id)).mappings().one()
        return _marketplace_user_out(conn, slug, row)


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


@router.get("/organization/users", response_model=list[OrganizationUserOut])
def list_organization_users(actor: Actor | None = Depends(get_optional_actor)):
    with get_connection() as conn:
        require_workspace_admin(conn, actor)
        rows = conn.execute(select(users).where(users.c.organization_id == DEFAULT_ORGANIZATION_ID).order_by(users.c.email)).mappings().all()
        return [_user_out(conn, row) for row in rows]


@router.post("/organization/users", response_model=OrganizationUserCreatedOut, status_code=201)
def create_organization_user(body: OrganizationUserCreate, actor: Actor | None = Depends(get_optional_actor)):
    now = now_ts()
    temp_password = generate_temp_password()
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        existing = conn.execute(select(users.c.id).where(users.c.email == body.email.lower())).one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail="User already exists")
        new_actor = upsert_user(conn, "local", body.email.lower(), body.email.lower(), body.displayName)
        conn.execute(insert(local_account_credentials).values(
            user_id=new_actor.user_id,
            password_hash=hash_password(temp_password),
            must_change_password=1,
            last_password_change=now,
        ))
        row = conn.execute(select(users).where(users.c.id == new_actor.user_id)).mappings().one()
        record_audit(conn, actor, "user.create", "user", str(new_actor.user_id))
        return {**_user_out(conn, row), "temporaryPassword": temp_password}


@router.post("/organization/users/{user_id}/reset-password")
def reset_organization_user_password(user_id: int, actor: Actor | None = Depends(get_optional_actor)):
    now = now_ts()
    temp_password = generate_temp_password()
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        user = conn.execute(select(users).where(users.c.id == user_id)).mappings().one_or_none()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        existing = conn.execute(select(local_account_credentials.c.user_id).where(local_account_credentials.c.user_id == user_id)).one_or_none()
        values = {"password_hash": hash_password(temp_password), "must_change_password": 1, "last_password_change": now}
        if existing is None:
            conn.execute(insert(local_account_credentials).values(user_id=user_id, **values))
        else:
            conn.execute(update(local_account_credentials).where(local_account_credentials.c.user_id == user_id).values(**values))
        record_audit(conn, actor, "user.reset_password", "user", str(user_id))
        return {"temporaryPassword": temp_password}


@router.put("/organization/users/{user_id}/role", response_model=OrganizationUserOut)
def update_organization_user_role(user_id: int, body: OrganizationUserRoleUpdate, actor: Actor | None = Depends(get_optional_actor)):
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        row = conn.execute(select(users).where(
            users.c.organization_id == DEFAULT_ORGANIZATION_ID,
            users.c.id == user_id,
        )).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        current_role = _organization_role_for_user(conn, user_id)
        if current_role == body.organizationRole:
            return _user_out(conn, row)
        if current_role == "organization_admin" and body.organizationRole == "viewer":
            admin_count = conn.execute(
                select(organization_role_grants.c.principal_id).where(
                    organization_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                    organization_role_grants.c.principal_type == "user",
                    organization_role_grants.c.role == "organization_admin",
                )
            ).all()
            if len(admin_count) <= 1:
                raise HTTPException(status_code=400, detail="At least one organization admin is required")
        conn.execute(delete(organization_role_grants).where(
            organization_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            organization_role_grants.c.principal_type == "user",
            organization_role_grants.c.principal_id == user_id,
            organization_role_grants.c.role == "organization_admin",
        ))
        if body.organizationRole == "organization_admin":
            conn.execute(insert(organization_role_grants).values(
                organization_id=DEFAULT_ORGANIZATION_ID,
                principal_type="user",
                principal_id=user_id,
                role="organization_admin",
                created_at=now_ts(),
            ))
        record_audit(conn, actor, "user.role_update", "user", str(user_id), {
            "organizationRole": body.organizationRole,
        })
        row = conn.execute(select(users).where(users.c.id == user_id)).mappings().one()
        return _user_out(conn, row)


@router.post("/organization/users/{user_id}/disable", response_model=OrganizationUserOut)
def disable_organization_user(user_id: int, actor: Actor | None = Depends(get_optional_actor)):
    return _set_user_disabled(user_id, actor, True)


@router.post("/organization/users/{user_id}/enable", response_model=OrganizationUserOut)
def enable_organization_user(user_id: int, actor: Actor | None = Depends(get_optional_actor)):
    return _set_user_disabled(user_id, actor, False)


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


def _marketplace_user_out(conn, marketplace_slug: str, row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "displayName": row["display_name"],
        "provider": row["provider"],
        "marketplaceRole": _marketplace_role_for_user(conn, marketplace_slug, row["id"]),
    }


def _marketplace_role_for_user(conn, marketplace_slug: str, user_id: int) -> str:
    roles = {
        row[0]
        for row in conn.execute(
            select(marketplace_role_grants.c.role).where(
                marketplace_role_grants.c.marketplace_slug == marketplace_slug,
                marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                marketplace_role_grants.c.principal_type == "user",
                marketplace_role_grants.c.principal_id == user_id,
            )
        ).all()
    }
    for role in ("marketplace_admin", "marketplace_maintainer", "viewer"):
        if role in roles:
            return role
    return "none"


def _user_out(conn, row) -> dict:
    cred = conn.execute(
        select(local_account_credentials.c.must_change_password).where(local_account_credentials.c.user_id == row["id"])
    ).one_or_none()
    return {
        "id": row["id"],
        "email": row["email"],
        "displayName": row["display_name"],
        "provider": row["provider"],
        "organizationRole": _organization_role_for_user(conn, row["id"]),
        "disabledAt": row["disabled_at"],
        "mustChangePassword": bool(cred and cred[0]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _organization_role_for_user(conn, user_id: int) -> str:
    admin = conn.execute(
        select(organization_role_grants.c.role).where(
            organization_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            organization_role_grants.c.principal_type == "user",
            organization_role_grants.c.principal_id == user_id,
            organization_role_grants.c.role == "organization_admin",
        )
    ).one_or_none()
    return "organization_admin" if admin else "viewer"


def _set_user_disabled(user_id: int, actor: Actor | None, disabled: bool) -> dict:
    with get_transaction() as conn:
        require_workspace_admin(conn, actor)
        row = conn.execute(select(users).where(users.c.id == user_id)).mappings().one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        now = now_ts()
        conn.execute(update(users).where(users.c.id == user_id).values(disabled_at=now if disabled else None, updated_at=now))
        row = conn.execute(select(users).where(users.c.id == user_id)).mappings().one()
        record_audit(conn, actor, "user.disable" if disabled else "user.enable", "user", str(user_id))
        return _user_out(conn, row)


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
        "allowlist": "allowlist_json",
    }
    values = {column: raw[key] for key, column in mapping.items() if key in raw}
    if "enabled" in values:
        values["enabled"] = 1 if values["enabled"] else 0
    if values.get("provider_type") == "trusted_headers":
        values["provider_type"] = "trusted_header"
    if "allowlist_json" in values:
        values["allowlist_json"] = json.dumps(values["allowlist_json"] or {})
    if values:
        values["updated_at"] = now
    return values


def _provider_out(row) -> dict:
    secret_env = row["client_secret_env_var"] or ""
    provider_type = row["provider_type"]
    callback_url = None
    if provider_type not in {"local", "trusted_header", "trusted_headers"}:
        callback_url = f"{get_settings().public_base_url.rstrip('/')}/auth/callback/{row['slug']}"
    return {
        "id": row["id"],
        "slug": row["slug"],
        "displayName": row["display_name"],
        "providerType": provider_type,
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
        "allowlist": json.loads(row["allowlist_json"] or "{}"),
        "loginUrl": f"/auth/login/{row['slug']}",
        "callbackUrl": callback_url,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
