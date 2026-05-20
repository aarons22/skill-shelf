import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Cookie, Header, HTTPException, Query, Request, status
from sqlalchemy import and_, insert, or_, select, update

from app.config import get_settings
from app.lib.session import COOKIE_NAME, read_payload
from app.models import (
    access_tokens,
    audit_events,
    groups,
    marketplace_role_grants,
    marketplaces,
    organizations,
    plugin_role_grants,
    user_groups,
    users,
    workspace_role_grants,
    workspace_settings,
)

AccessMode = Literal["public", "authenticated", "restricted"]

DEFAULT_ORGANIZATION_ID = 1
ORGANIZATION_ADMIN = "organization_admin"
WORKSPACE_ADMIN = ORGANIZATION_ADMIN
MARKETPLACE_ADMIN = "marketplace_admin"
MARKETPLACE_MAINTAINER = "marketplace_maintainer"
PLUGIN_MAINTAINER = "plugin_maintainer"
VIEWER = "viewer"


@dataclass(frozen=True)
class Actor:
    user_id: int | None
    email: str
    display_name: str
    anonymous: bool = False


@dataclass(frozen=True)
class ReadToken:
    id: int
    scope: str
    marketplace_slug: str | None


def now_ts() -> int:
    return int(time.time())


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return "ssrt_" + secrets.token_urlsafe(32)


def ensure_default_organization(conn) -> dict[str, Any]:
    row = conn.execute(select(organizations).where(organizations.c.id == DEFAULT_ORGANIZATION_ID)).mappings().one_or_none()
    if row is not None:
        return dict(row)
    now = now_ts()
    conn.execute(insert(organizations).values(
        id=DEFAULT_ORGANIZATION_ID,
        slug="default",
        display_name="Default Organization",
        created_at=now,
        updated_at=now,
    ))
    return {
        "id": DEFAULT_ORGANIZATION_ID,
        "slug": "default",
        "display_name": "Default Organization",
        "created_at": now,
        "updated_at": now,
    }


def record_audit(conn, actor: Actor | None, action: str, target_type: str, target_id: str, metadata: dict[str, Any] | None = None) -> None:
    ensure_default_organization(conn)
    conn.execute(insert(audit_events).values(
        organization_id=DEFAULT_ORGANIZATION_ID,
        actor_user_id=actor.user_id if actor else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=json.dumps(metadata or {}),
        created_at=now_ts(),
    ))


def ensure_workspace_settings(conn) -> dict[str, Any]:
    ensure_default_organization(conn)
    row = conn.execute(select(workspace_settings).where(workspace_settings.c.id == 1)).mappings().one_or_none()
    if row is not None:
        return dict(row)
    now = now_ts()
    conn.execute(insert(workspace_settings).values(
        id=1,
        organization_id=DEFAULT_ORGANIZATION_ID,
        access_mode="public",
        marketplace_creation="authenticated",
        created_at=now,
        updated_at=now,
    ))
    return {
        "id": 1,
        "access_mode": "public",
        "marketplace_creation": "authenticated",
        "created_at": now,
        "updated_at": now,
    }


def upsert_user(conn, provider: str, subject: str, email: str, display_name: str) -> Actor:
    ensure_default_organization(conn)
    now = now_ts()
    row = conn.execute(
        select(users).where(
            users.c.organization_id == DEFAULT_ORGANIZATION_ID,
            users.c.provider == provider,
            users.c.provider_subject == subject,
        )
    ).mappings().one_or_none()
    if row is None:
        conn.execute(insert(users).values(
            organization_id=DEFAULT_ORGANIZATION_ID,
            provider=provider,
            provider_subject=subject,
            email=email,
            display_name=display_name,
            created_at=now,
            updated_at=now,
        ))
    else:
        conn.execute(
            update(users).where(users.c.id == row["id"]).values(
                email=email,
                display_name=display_name,
                updated_at=now,
            )
        )
    user = conn.execute(
        select(users).where(
            users.c.organization_id == DEFAULT_ORGANIZATION_ID,
            users.c.provider == provider,
            users.c.provider_subject == subject,
        )
    ).mappings().one()
    if user["disabled_at"] is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    existing_admin = conn.execute(
        select(workspace_role_grants.c.role).where(workspace_role_grants.c.role == WORKSPACE_ADMIN)
    ).one_or_none()
    if existing_admin is None:
        conn.execute(insert(workspace_role_grants).values(
            organization_id=DEFAULT_ORGANIZATION_ID,
            principal_type="user",
            principal_id=user["id"],
            role=ORGANIZATION_ADMIN,
            created_at=now,
        ))
    return Actor(user_id=user["id"], email=user["email"], display_name=user["display_name"])


def sync_header_groups(conn, actor: Actor, provider: str, group_names: list[str]) -> None:
    if actor.user_id is None:
        return
    now = now_ts()
    for name in group_names:
        key = name.strip()
        if not key:
            continue
        row = conn.execute(
            select(groups).where(
                groups.c.organization_id == DEFAULT_ORGANIZATION_ID,
                groups.c.provider == provider,
                groups.c.provider_key == key,
            )
        ).mappings().one_or_none()
        if row is None:
            conn.execute(insert(groups).values(
                organization_id=DEFAULT_ORGANIZATION_ID,
                provider=provider,
                provider_key=key,
                display_name=key,
                created_at=now,
                updated_at=now,
            ))
            row = conn.execute(
                select(groups).where(
                    groups.c.organization_id == DEFAULT_ORGANIZATION_ID,
                    groups.c.provider == provider,
                    groups.c.provider_key == key,
                )
            ).mappings().one()
        exists = conn.execute(
            select(user_groups.c.user_id).where(
                user_groups.c.user_id == actor.user_id,
                user_groups.c.group_id == row["id"],
            )
        ).one_or_none()
        if exists is None:
            conn.execute(insert(user_groups).values(
                organization_id=DEFAULT_ORGANIZATION_ID,
                user_id=actor.user_id,
                group_id=row["id"],
                created_at=now,
            ))


def actor_from_headers(
    conn,
    x_skillshelf_user_email: str | None,
    x_skillshelf_user_name: str | None,
    x_skillshelf_user_id: str | None,
    x_skillshelf_groups: str | None,
) -> Actor | None:
    if not x_skillshelf_user_email:
        return None
    provider = "headers"
    subject = x_skillshelf_user_id or x_skillshelf_user_email
    display_name = x_skillshelf_user_name or x_skillshelf_user_email
    actor = upsert_user(conn, provider, subject, x_skillshelf_user_email, display_name)
    if x_skillshelf_groups:
        sync_header_groups(conn, actor, provider, x_skillshelf_groups.split(","))
    return actor


def get_optional_actor(
    request: Request,
    skillshelf_session: str | None = Cookie(default=None),
    x_skillshelf_user_email: str | None = Header(default=None),
    x_skillshelf_user_name: str | None = Header(default=None),
    x_skillshelf_user_id: str | None = Header(default=None),
    x_skillshelf_groups: str | None = Header(default=None),
) -> Actor | None:
    actor = getattr(request.state, "actor", None)
    if actor is not None:
        return actor
    from app.db import get_transaction

    session = read_payload(skillshelf_session)
    if session and session.get("user_id"):
        with get_transaction() as conn:
            user = conn.execute(
                select(users).where(
                    users.c.organization_id == DEFAULT_ORGANIZATION_ID,
                    users.c.id == int(session["user_id"]),
                )
            ).mappings().one_or_none()
            if user is not None and user["disabled_at"] is None:
                actor = Actor(user_id=user["id"], email=user["email"], display_name=user["display_name"])
                request.state.actor = actor
                return actor
    with get_transaction() as conn:
        actor = None
        if get_settings().trusted_header_auth or get_settings().node_env == "development":
            actor = actor_from_headers(
                conn,
                x_skillshelf_user_email,
                x_skillshelf_user_name,
                x_skillshelf_user_id,
                x_skillshelf_groups,
            )
    request.state.actor = actor
    return actor


def get_required_actor(
    request: Request,
    skillshelf_session: str | None = Cookie(default=None),
    x_skillshelf_user_email: str | None = Header(default=None),
    x_skillshelf_user_name: str | None = Header(default=None),
    x_skillshelf_user_id: str | None = Header(default=None),
    x_skillshelf_groups: str | None = Header(default=None),
) -> Actor:
    actor = get_optional_actor(
        request=request,
        skillshelf_session=skillshelf_session,
        x_skillshelf_user_email=x_skillshelf_user_email,
        x_skillshelf_user_name=x_skillshelf_user_name,
        x_skillshelf_user_id=x_skillshelf_user_id,
        x_skillshelf_groups=x_skillshelf_groups,
    )
    if actor is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return actor


def get_read_token(
    conn,
    authorization: str | None = None,
    access_token: str | None = None,
) -> ReadToken | None:
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    elif access_token:
        raw = access_token
    if not raw:
        return None
    row = conn.execute(
        select(access_tokens).where(
            access_tokens.c.token_hash == token_hash(raw),
            access_tokens.c.revoked_at.is_(None),
            or_(access_tokens.c.expires_at.is_(None), access_tokens.c.expires_at > now_ts()),
        )
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return ReadToken(id=row["id"], scope=row["scope"], marketplace_slug=row["marketplace_slug"])


def _principal_filters(conn, actor: Actor):
    if actor.user_id is None:
        return []
    group_ids = [
        row[0]
        for row in conn.execute(
            select(user_groups.c.group_id).where(user_groups.c.organization_id == DEFAULT_ORGANIZATION_ID, user_groups.c.user_id == actor.user_id)
        ).all()
    ]
    filters = [
        and_(
            workspace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            workspace_role_grants.c.principal_type == "user",
            workspace_role_grants.c.principal_id == actor.user_id,
        )
    ]
    filters.extend(
        and_(
            workspace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            workspace_role_grants.c.principal_type == "group",
            workspace_role_grants.c.principal_id == gid,
        )
        for gid in group_ids
    )
    return filters


def is_workspace_admin(conn, actor: Actor | None) -> bool:
    if actor is None:
        return False
    if actor.anonymous:
        return True
    filters = _principal_filters(conn, actor)
    if not filters:
        return False
    return conn.execute(
        select(workspace_role_grants.c.role).where(
            workspace_role_grants.c.role.in_([ORGANIZATION_ADMIN, "workspace_admin"]),
            or_(*filters),
        )
    ).one_or_none() is not None


def _marketplace_filters(table, conn, actor: Actor, marketplace_slug: str):
    if actor.user_id is None:
        return []
    group_ids = [
        row[0]
        for row in conn.execute(
            select(user_groups.c.group_id).where(user_groups.c.organization_id == DEFAULT_ORGANIZATION_ID, user_groups.c.user_id == actor.user_id)
        ).all()
    ]
    filters = [
        and_(
            table.c.organization_id == DEFAULT_ORGANIZATION_ID,
            table.c.marketplace_slug == marketplace_slug,
            table.c.principal_type == "user",
            table.c.principal_id == actor.user_id,
        )
    ]
    filters.extend(
        and_(
            table.c.organization_id == DEFAULT_ORGANIZATION_ID,
            table.c.marketplace_slug == marketplace_slug,
            table.c.principal_type == "group",
            table.c.principal_id == gid,
        )
        for gid in group_ids
    )
    return filters


def has_marketplace_role(conn, actor: Actor | None, marketplace_slug: str, roles: set[str]) -> bool:
    if actor is None:
        return False
    if is_workspace_admin(conn, actor):
        return True
    filters = _marketplace_filters(marketplace_role_grants, conn, actor, marketplace_slug)
    if not filters:
        return False
    return conn.execute(
        select(marketplace_role_grants.c.role).where(
            marketplace_role_grants.c.role.in_(roles),
            or_(*filters),
        )
    ).one_or_none() is not None


def has_plugin_role(conn, actor: Actor | None, marketplace_slug: str, plugin_slug: str, roles: set[str]) -> bool:
    if actor is None:
        return False
    if has_marketplace_role(conn, actor, marketplace_slug, {MARKETPLACE_ADMIN, MARKETPLACE_MAINTAINER}):
        return True
    if actor.user_id is None:
        return False
    group_ids = [
        row[0]
        for row in conn.execute(
            select(user_groups.c.group_id).where(user_groups.c.organization_id == DEFAULT_ORGANIZATION_ID, user_groups.c.user_id == actor.user_id)
        ).all()
    ]
    filters = [
        and_(
            plugin_role_grants.c.marketplace_slug == marketplace_slug,
            plugin_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            plugin_role_grants.c.plugin_slug == plugin_slug,
            plugin_role_grants.c.principal_type == "user",
            plugin_role_grants.c.principal_id == actor.user_id,
        )
    ]
    filters.extend(
        and_(
            plugin_role_grants.c.marketplace_slug == marketplace_slug,
            plugin_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            plugin_role_grants.c.plugin_slug == plugin_slug,
            plugin_role_grants.c.principal_type == "group",
            plugin_role_grants.c.principal_id == gid,
        )
        for gid in group_ids
    )
    return conn.execute(
        select(plugin_role_grants.c.role).where(plugin_role_grants.c.role.in_(roles), or_(*filters))
    ).one_or_none() is not None


def anonymous_admin_if_public(conn) -> Actor | None:
    settings = ensure_workspace_settings(conn)
    if settings["access_mode"] == "public" or get_settings().node_env == "development":
        return Actor(user_id=None, email="anonymous@skillshelf.local", display_name="Anonymous", anonymous=True)
    return None


def require_workspace_admin(conn, actor: Actor | None) -> Actor:
    actor = actor or anonymous_admin_if_public(conn)
    if not is_workspace_admin(conn, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization admin required")
    return actor


def require_marketplace_admin(conn, actor: Actor | None, marketplace_slug: str) -> Actor:
    actor = actor or anonymous_admin_if_public(conn)
    if not has_marketplace_role(conn, actor, marketplace_slug, {MARKETPLACE_ADMIN}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Marketplace admin required")
    return actor


def require_marketplace_write(conn, actor: Actor | None, marketplace_slug: str, plugin_slug: str | None = None) -> Actor:
    actor = actor or anonymous_admin_if_public(conn)
    if plugin_slug and has_plugin_role(conn, actor, marketplace_slug, plugin_slug, {PLUGIN_MAINTAINER}):
        return actor
    if not has_marketplace_role(conn, actor, marketplace_slug, {MARKETPLACE_ADMIN, MARKETPLACE_MAINTAINER}):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Marketplace write access required")
    return actor


def can_create_marketplace(conn, actor: Actor | None) -> bool:
    settings = ensure_workspace_settings(conn)
    if settings["access_mode"] == "public" and actor is None:
        return True
    if actor is None:
        return False
    if is_workspace_admin(conn, actor):
        return True
    return settings["marketplace_creation"] == "authenticated"


def can_read_marketplace(conn, actor: Actor | None, marketplace_slug: str, read_token: ReadToken | None = None) -> bool:
    settings = ensure_workspace_settings(conn)
    if read_token is not None:
        return read_token.scope == "marketplace_read" and (
            read_token.marketplace_slug is None or read_token.marketplace_slug == marketplace_slug
        )
    if settings["access_mode"] == "public":
        return True
    if actor is None:
        return False
    if settings["access_mode"] == "authenticated":
        row = conn.execute(select(marketplaces.c.visibility).where(marketplaces.c.slug == marketplace_slug)).one_or_none()
        if row and row[0] == "restricted":
            return has_marketplace_role(conn, actor, marketplace_slug, {MARKETPLACE_ADMIN, MARKETPLACE_MAINTAINER, VIEWER})
        return True
    return has_marketplace_role(conn, actor, marketplace_slug, {MARKETPLACE_ADMIN, MARKETPLACE_MAINTAINER, VIEWER})


def require_marketplace_read(conn, actor: Actor | None, marketplace_slug: str, read_token: ReadToken | None = None) -> None:
    if not can_read_marketplace(conn, actor, marketplace_slug, read_token):
        if actor is None and read_token is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Marketplace read access required")


def visible_marketplace_condition(conn, actor: Actor | None):
    settings = ensure_workspace_settings(conn)
    if settings["access_mode"] == "public":
        return None
    if actor is None:
        return marketplaces.c.slug == "__none__"
    if settings["access_mode"] == "authenticated":
        if is_workspace_admin(conn, actor):
            return None
        return or_(
            marketplaces.c.visibility == "workspace",
            marketplaces.c.slug.in_(_granted_marketplace_slugs(conn, actor, {MARKETPLACE_ADMIN, MARKETPLACE_MAINTAINER, VIEWER})),
        )
    if is_workspace_admin(conn, actor):
        return None
    return marketplaces.c.slug.in_(_granted_marketplace_slugs(conn, actor, {MARKETPLACE_ADMIN, MARKETPLACE_MAINTAINER, VIEWER}))


def _granted_marketplace_slugs(conn, actor: Actor, roles: set[str]) -> list[str]:
    if actor.user_id is None:
        return []
    group_ids = [
        row[0]
        for row in conn.execute(
            select(user_groups.c.group_id).where(user_groups.c.organization_id == DEFAULT_ORGANIZATION_ID, user_groups.c.user_id == actor.user_id)
        ).all()
    ]
    conditions = [
        and_(
            marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            marketplace_role_grants.c.principal_type == "user",
            marketplace_role_grants.c.principal_id == actor.user_id,
        )
    ]
    conditions.extend(
        and_(
            marketplace_role_grants.c.organization_id == DEFAULT_ORGANIZATION_ID,
            marketplace_role_grants.c.principal_type == "group",
            marketplace_role_grants.c.principal_id == gid,
        )
        for gid in group_ids
    )
    rows = conn.execute(
        select(marketplace_role_grants.c.marketplace_slug).where(
            marketplace_role_grants.c.role.in_(roles),
            or_(*conditions),
        )
    ).all()
    return [row[0] for row in rows]


def public_read_dependencies(
    request: Request,
    authorization: str | None = Header(default=None),
    access_token: str | None = Query(default=None),
    x_skillshelf_user_email: str | None = Header(default=None),
    x_skillshelf_user_name: str | None = Header(default=None),
    x_skillshelf_user_id: str | None = Header(default=None),
    x_skillshelf_groups: str | None = Header(default=None),
):
    from app.db import get_transaction

    with get_transaction() as conn:
        actor = actor_from_headers(conn, x_skillshelf_user_email, x_skillshelf_user_name, x_skillshelf_user_id, x_skillshelf_groups)
        request.state.actor = actor
        request.state.read_token = get_read_token(conn, authorization, access_token)
    return None
