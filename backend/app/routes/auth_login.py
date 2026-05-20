import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update

from app.config import get_settings
from app.db import get_connection, get_transaction
from app.lib.auth import DEFAULT_ORGANIZATION_ID, sync_header_groups, upsert_user
from app.lib.local_accounts import hash_password, verify_password
from app.lib.provider_allowlist import enforce
from app.lib.session import COOKIE_NAME, STATE_COOKIE_NAME, read_payload, sign_payload
from app.models import auth_providers, local_account_credentials, users
from app.schemas import ChangePasswordIn, LoginLocalIn, PublicAuthProviderOut

router = APIRouter(tags=["auth"])


def _provider_sort_key(row) -> tuple[int, str]:
    return (0 if row["provider_type"] == "local" else 1, row["display_name"].lower())


@router.get("/auth/login")
def login_index():
    with get_connection() as conn:
        rows = conn.execute(
            select(auth_providers).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.enabled == 1,
            )
        ).mappings().all()
    rows = sorted(rows, key=_provider_sort_key)
    if len(rows) == 1 and rows[0]["provider_type"] not in {"local", "trusted_header", "trusted_headers"}:
        return RedirectResponse(f"/auth/login/{rows[0]['slug']}", status_code=302)
    return {
        "providers": [
            {"slug": row["slug"], "displayName": row["display_name"], "loginUrl": f"/auth/login/{row['slug']}"}
            for row in rows
        ]
    }


@router.get("/api/auth/providers", response_model=list[PublicAuthProviderOut])
def public_auth_providers():
    with get_connection() as conn:
        rows = conn.execute(
            select(auth_providers).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.enabled == 1,
            )
        ).mappings().all()
    return [_public_provider(row) for row in sorted(rows, key=_provider_sort_key)]


@router.post("/auth/login/local")
def login_local(body: LoginLocalIn, request: Request):
    with get_connection() as conn:
        user = conn.execute(
            select(users).where(
                users.c.organization_id == DEFAULT_ORGANIZATION_ID,
                users.c.provider == "local",
                users.c.provider_subject == body.email.lower(),
            )
        ).mappings().one_or_none()
        if user is None:
            raise HTTPException(status_code=401, detail="Sign-in failed")
        if user["disabled_at"] is not None:
            raise HTTPException(status_code=403, detail="User is disabled")
        credential = conn.execute(
            select(local_account_credentials).where(local_account_credentials.c.user_id == user["id"])
        ).mappings().one_or_none()
        if credential is None or not verify_password(body.password, credential["password_hash"]):
            raise HTTPException(status_code=401, detail="Sign-in failed")
    response = JSONResponse({"mustChangePassword": bool(credential["must_change_password"])})
    _set_session_cookie(response, request, user["id"], "local")
    return response


@router.post("/auth/change-password")
def change_password(body: ChangePasswordIn, request: Request):
    payload = read_payload(request.cookies.get(COOKIE_NAME))
    if not payload or not payload.get("user_id"):
        raise HTTPException(status_code=401, detail="Authentication required")
    user_id = int(payload["user_id"])
    with get_transaction() as conn:
        credential = conn.execute(
            select(local_account_credentials).where(local_account_credentials.c.user_id == user_id)
        ).mappings().one_or_none()
        if credential is None or not verify_password(body.currentPassword, credential["password_hash"]):
            raise HTTPException(status_code=401, detail="Sign-in failed")
        conn.execute(
            update(local_account_credentials).where(local_account_credentials.c.user_id == user_id).values(
                password_hash=hash_password(body.newPassword),
                must_change_password=0,
                last_password_change=int(__import__("time").time()),
            )
        )
    return {"ok": True}


@router.get("/auth/login/{provider_slug}")
def start_login(provider_slug: str, request: Request):
    provider = _provider_or_404(provider_slug)
    if not provider["enabled"]:
        raise HTTPException(status_code=404, detail="Auth provider not found")
    if provider["provider_type"] in {"local", "trusted_header", "trusted_headers"}:
        raise HTTPException(status_code=400, detail="This provider does not use redirect login")
    secret = os.getenv(provider["client_secret_env_var"] or "")
    if not provider["client_id"] or not secret:
        raise HTTPException(status_code=400, detail="Auth provider is missing client ID or configured secret env var")
    state = secrets.token_urlsafe(24)
    return_to = request.query_params.get("return_to") or "/manage"
    authorization_url = _authorization_url(provider)
    callback_url = _callback_url(provider_slug)
    params = {
        "client_id": provider["client_id"],
        "redirect_uri": callback_url,
        "response_type": "code",
        "scope": provider["scopes"],
        "state": state,
    }
    response = RedirectResponse(f"{authorization_url}?{urlencode(params)}", status_code=302)
    response.set_cookie(
        STATE_COOKIE_NAME,
        sign_payload({"state": state, "provider": provider_slug, "return_to": return_to}, max_age_seconds=600),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=600,
    )
    return response


@router.get("/auth/callback/{provider_slug}", name="auth_callback")
def auth_callback(provider_slug: str, request: Request, code: str, state: str, response: Response):
    state_payload = read_payload(request.cookies.get(STATE_COOKIE_NAME))
    if not state_payload or state_payload.get("state") != state or state_payload.get("provider") != provider_slug:
        raise HTTPException(status_code=400, detail="Invalid login state")
    provider = _provider_or_404(provider_slug)
    secret = os.getenv(provider["client_secret_env_var"] or "")
    if not provider["client_id"] or not secret:
        raise HTTPException(status_code=400, detail="Auth provider is missing client ID or configured secret env var")

    callback_url = _callback_url(provider_slug)
    token_payload = _exchange_code(provider, code, callback_url, secret)
    profile = _load_profile(provider, token_payload)
    with get_transaction() as conn:
        enforce(provider, profile, profile["groups"])
        actor = upsert_user(conn, provider_slug, profile["subject"], profile["email"], profile["name"])
        sync_header_groups(conn, actor, provider_slug, profile["groups"])

    redirect = RedirectResponse(state_payload.get("return_to") or "/manage", status_code=302)
    _set_session_cookie(redirect, request, actor.user_id, provider_slug)
    redirect.delete_cookie(STATE_COOKIE_NAME)
    return redirect


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    response.delete_cookie(STATE_COOKIE_NAME)
    return {"ok": True}


def _provider_or_404(provider_slug: str):
    with get_connection() as conn:
        row = conn.execute(
            select(auth_providers).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.slug == provider_slug,
            )
        ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Auth provider not found")
    return dict(row)


def _callback_url(provider_slug: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/auth/callback/{provider_slug}"


def _authorization_url(provider: dict) -> str:
    if provider["provider_type"] == "github":
        return "https://github.com/login/oauth/authorize"
    if provider["authorization_url"]:
        return provider["authorization_url"]
    metadata = _oidc_metadata(provider)
    return metadata["authorization_endpoint"]


def _token_url(provider: dict) -> str:
    if provider["provider_type"] == "github":
        return "https://github.com/login/oauth/access_token"
    if provider["token_url"]:
        return provider["token_url"]
    metadata = _oidc_metadata(provider)
    return metadata["token_endpoint"]


def _userinfo_url(provider: dict) -> str | None:
    if provider["provider_type"] == "github":
        return "https://api.github.com/user"
    if provider["userinfo_url"]:
        return provider["userinfo_url"]
    metadata = _oidc_metadata(provider)
    return metadata.get("userinfo_endpoint")


def _oidc_metadata(provider: dict) -> dict:
    if not provider["issuer_url"]:
        raise HTTPException(status_code=400, detail="OIDC provider requires an issuer URL or explicit endpoints")
    url = provider["issuer_url"].rstrip("/") + "/.well-known/openid-configuration"
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    return r.json()


def _exchange_code(provider: dict, code: str, redirect_uri: str, secret: str) -> dict:
    r = httpx.post(
        _token_url(provider),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": provider["client_id"],
            "client_secret": secret,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _load_profile(provider: dict, token_payload: dict) -> dict:
    access_token = token_payload.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Provider did not return an access token")
    userinfo_url = _userinfo_url(provider)
    if not userinfo_url:
        raise HTTPException(status_code=400, detail="OIDC provider did not expose a userinfo endpoint")
    r = httpx.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if provider["provider_type"] == "github":
        email = data.get("email") or f"{data['id']}+github@users.noreply.github.com"
        return {"subject": str(data["id"]), "email": email, "name": data.get("name") or data.get("login") or email, "username": data.get("login"), "groups": []}
    email = data.get("email")
    subject = data.get("sub")
    if not email or not subject:
        raise HTTPException(status_code=400, detail="OIDC profile must include sub and email claims")
    group_claim = provider.get("group_claim")
    groups = data.get(group_claim, []) if group_claim else []
    if isinstance(groups, str):
        groups = [groups]
    return {"subject": str(subject), "email": email, "name": data.get("name") or email, "groups": [str(g) for g in groups]}


def _public_provider(row) -> dict:
    provider_type = row["provider_type"]
    if provider_type == "local":
        kind = "credentials"
    elif provider_type in {"trusted_header", "trusted_headers"}:
        kind = "trusted_header"
    else:
        kind = "redirect"
    return {
        "slug": row["slug"],
        "displayName": row["display_name"],
        "providerType": provider_type,
        "kind": kind,
        "loginUrl": f"/auth/login/{row['slug']}",
    }


def _set_session_cookie(response: Response, request: Request, user_id: int, provider: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        sign_payload({"user_id": user_id, "provider": provider}, max_age_seconds=60 * 60 * 24 * 14),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=60 * 60 * 24 * 14,
    )
