import json

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select, update

from app.db import get_transaction
from app.lib.auth import DEFAULT_ORGANIZATION_ID, ORGANIZATION_ADMIN, ensure_default_organization, now_ts, upsert_user
from app.lib.local_accounts import hash_password
from app.lib.session import COOKIE_NAME, sign_payload
from app.lib.setup_state import is_required, mark_completed
from app.models import auth_providers, local_account_credentials, organization_role_grants, organization_settings, organizations, users
from app.schemas import OrganizationSetupIn, SetupStatusOut

router = APIRouter(prefix="/api", tags=["setup"])


@router.get("/setup/status", response_model=SetupStatusOut)
def setup_status():
    with get_transaction() as conn:
        ensure_default_organization(conn)
        required = is_required(conn)
        return {"required": required, "completed": not required}


@router.post("/organization/setup")
def complete_setup(body: OrganizationSetupIn, request: Request):
    with get_transaction() as conn:
        ensure_default_organization(conn)
        if not is_required(conn):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Setup already complete")
        now = now_ts()
        conn.execute(
            update(organizations)
            .where(organizations.c.id == DEFAULT_ORGANIZATION_ID)
            .values(
                display_name=body.displayName,
                owner_name=body.ownerName,
                owner_email=body.ownerEmail,
                updated_at=now,
            )
        )
        settings = conn.execute(
            select(organization_settings).where(organization_settings.c.id == 1)
        ).mappings().one_or_none()
        if settings is None:
            conn.execute(
                insert(organization_settings).values(
                    id=1,
                    organization_id=DEFAULT_ORGANIZATION_ID,
                    access_mode=body.accessMode,
                    marketplace_creation=body.marketplaceCreation,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            conn.execute(
                update(organization_settings)
                .where(organization_settings.c.id == 1)
                .values(access_mode=body.accessMode, marketplace_creation=body.marketplaceCreation, updated_at=now)
            )

        provider_slug = body.provider.slug or body.provider.provider
        provider_type = body.provider.provider
        if provider_type == "trusted_headers":
            provider_type = "trusted_header"
        if provider_type == "local":
            provider_slug = "local"
        provider_display_name = body.provider.displayName or "Local Accounts"
        exists = conn.execute(
            select(auth_providers.c.id).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.slug == provider_slug,
            )
        ).one_or_none()
        provider_values = {
            "organization_id": DEFAULT_ORGANIZATION_ID,
            "slug": provider_slug,
            "display_name": provider_display_name,
            "provider_type": provider_type,
            "enabled": 1,
            "client_id": body.provider.clientId,
            "client_secret_env_var": body.provider.clientSecretEnvVar,
            "issuer_url": body.provider.issuerUrl,
            "authorization_url": body.provider.authorizationUrl,
            "token_url": body.provider.tokenUrl,
            "userinfo_url": body.provider.userinfoUrl,
            "scopes": body.provider.scopes,
            "group_claim": body.provider.groupClaim,
            "allowed_orgs": None,
            "allowlist_json": json.dumps(body.provider.allowlist or {}),
            "updated_at": now,
        }
        if exists is None:
            conn.execute(insert(auth_providers).values(**provider_values, created_at=now))
        else:
            conn.execute(update(auth_providers).where(auth_providers.c.id == exists[0]).values(**provider_values))

        actor = None
        if provider_type == "local":
            if body.provider.admin is None:
                raise HTTPException(status_code=400, detail="Local setup requires an admin account")
            admin = body.provider.admin
            actor = upsert_user(conn, "local", admin.email.lower(), admin.email.lower(), admin.displayName)
            conn.execute(
                insert(local_account_credentials).values(
                    user_id=actor.user_id,
                    password_hash=hash_password(admin.password),
                    must_change_password=0,
                    last_password_change=now,
                )
            )
        else:
            session = request.cookies.get(COOKIE_NAME)
            from app.lib.session import read_payload

            payload = read_payload(session)
            if not payload or not payload.get("user_id"):
                raise HTTPException(status_code=400, detail="External setup requires a signed-in user")
            user_id = int(payload["user_id"])
            user = conn.execute(
                select(users.c.id).where(
                    users.c.organization_id == DEFAULT_ORGANIZATION_ID,
                    users.c.id == user_id,
                    users.c.disabled_at.is_(None),
                )
            ).one_or_none()
            if user is None:
                raise HTTPException(status_code=400, detail="Invalid setup session")
            actor_id = user_id
            actor = type("ActorRef", (), {"user_id": actor_id})()

        admin_exists = conn.execute(
            select(organization_role_grants.c.role).where(
                organization_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
                organization_role_grants.c.principal_type == "user",
                organization_role_grants.c.principal_id == actor.user_id,
                organization_role_grants.c.role == ORGANIZATION_ADMIN,
            )
        ).one_or_none()
        if admin_exists is None:
            conn.execute(
                insert(organization_role_grants).values(
                    organization_id=DEFAULT_ORGANIZATION_ID,
                    principal_type="user",
                    principal_id=actor.user_id,
                    role=ORGANIZATION_ADMIN,
                    created_at=now,
                )
            )
        if conn.execute(select(auth_providers.c.id).where(auth_providers.c.enabled == 1)).one_or_none() is None:
            raise HTTPException(status_code=400, detail="At least one auth provider is required")
        if conn.execute(select(organization_role_grants.c.role).where(organization_role_grants.c.role == ORGANIZATION_ADMIN)).one_or_none() is None:
            raise HTTPException(status_code=400, detail="At least one organization admin is required")
        mark_completed(conn)
        user_row = None
        if actor.user_id is not None:
            user_row = conn.execute(select(users).where(users.c.id == actor.user_id)).mappings().one()

    response = JSONResponse(
        {
            "authenticated": True,
            "id": user_row["id"],
            "email": user_row["email"],
            "displayName": user_row["display_name"],
            "organizationAdmin": True,
            "workspaceAdmin": True,
            "bootstrapRequired": False,
            "bootstrapCompleted": True,
            "mustChangePassword": False,
            "accessMode": body.accessMode,
            "marketplaceCreation": body.marketplaceCreation,
            "loginConfigured": True,
        }
    )
    response.set_cookie(
        COOKIE_NAME,
        sign_payload({"user_id": user_row["id"], "provider": user_row["provider"]}, max_age_seconds=60 * 60 * 24 * 14),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=60 * 60 * 24 * 14,
    )
    return response
