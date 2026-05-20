import os
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from app.db import get_connection, get_transaction
from app.lib.auth import DEFAULT_ORGANIZATION_ID, sync_header_groups, upsert_user
from app.lib.session import COOKIE_NAME, STATE_COOKIE_NAME, read_payload, sign_payload
from app.models import auth_providers

router = APIRouter(tags=["auth"])


@router.get("/auth/login")
def login_index():
    with get_connection() as conn:
        rows = conn.execute(
            select(auth_providers).where(
                auth_providers.c.organization_id == DEFAULT_ORGANIZATION_ID,
                auth_providers.c.enabled == 1,
            ).order_by(auth_providers.c.display_name)
        ).mappings().all()
    if len(rows) == 1:
        return RedirectResponse(f"/auth/login/{rows[0]['slug']}", status_code=302)
    return {
        "providers": [
            {"slug": row["slug"], "displayName": row["display_name"], "loginUrl": f"/auth/login/{row['slug']}"}
            for row in rows
        ]
    }


@router.get("/auth/login/{provider_slug}")
def start_login(provider_slug: str, request: Request):
    provider = _provider_or_404(provider_slug)
    if not provider["enabled"]:
        raise HTTPException(status_code=404, detail="Auth provider not found")
    secret = os.getenv(provider["client_secret_env_var"] or "")
    if not provider["client_id"] or not secret:
        raise HTTPException(status_code=400, detail="Auth provider is missing client ID or configured secret env var")
    state = secrets.token_urlsafe(24)
    authorization_url = _authorization_url(provider)
    callback_url = str(request.url_for("auth_callback", provider_slug=provider_slug))
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
        sign_payload({"state": state, "provider": provider_slug}, max_age_seconds=600),
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

    callback_url = str(request.url_for("auth_callback", provider_slug=provider_slug))
    token_payload = _exchange_code(provider, code, callback_url, secret)
    profile = _load_profile(provider, token_payload)
    with get_transaction() as conn:
        actor = upsert_user(conn, provider_slug, profile["subject"], profile["email"], profile["name"])
        sync_header_groups(conn, actor, provider_slug, profile["groups"])

    redirect = RedirectResponse("/manage", status_code=302)
    redirect.set_cookie(
        COOKIE_NAME,
        sign_payload({"user_id": actor.user_id, "provider": provider_slug}, max_age_seconds=60 * 60 * 24 * 14),
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        max_age=60 * 60 * 24 * 14,
    )
    redirect.delete_cookie(STATE_COOKIE_NAME)
    return redirect


@router.post("/auth/logout")
def logout():
    response = RedirectResponse("/", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    response.delete_cookie(STATE_COOKIE_NAME)
    return response


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
        return {"subject": str(data["id"]), "email": email, "name": data.get("name") or data.get("login") or email, "groups": []}
    email = data.get("email")
    subject = data.get("sub")
    if not email or not subject:
        raise HTTPException(status_code=400, detail="OIDC profile must include sub and email claims")
    group_claim = provider.get("group_claim")
    groups = data.get(group_claim, []) if group_claim else []
    if isinstance(groups, str):
        groups = [groups]
    return {"subject": str(subject), "email": email, "name": data.get("name") or email, "groups": [str(g) for g in groups]}
