"""
Git smart-HTTP serving for /m/{slug}/git/repo.git/*

Delegates to dulwich WSGI app (cached in git_store) via a2wsgi.
Read-only — only git-upload-pack is served.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.db import get_connection
from app.lib.git_store import get_wsgi_app
from app.models import marketplaces

router = APIRouter(tags=["git"])


@router.api_route("/m/{slug}/git/repo.git/{path:path}", methods=["GET", "POST"])
async def git_smart_http(slug: str, path: str, request: Request):
    with get_connection() as conn:
        exists = conn.execute(
            select(marketplaces.c.slug).where(marketplaces.c.slug == slug)
        ).one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Marketplace not found")

    wsgi_app = get_wsgi_app(slug)
    if wsgi_app is None:
        raise HTTPException(status_code=404, detail="Git repo not initialized")

    # Rewrite scope: dulwich expects the sub-path after /repo.git (e.g. /info/refs)
    sub_path = f"/{path}" if path else "/"
    qs = request.url.query
    scope = dict(request.scope)
    scope["path"] = sub_path
    scope["raw_path"] = sub_path.encode()
    scope["query_string"] = qs.encode() if qs else b""

    return await wsgi_app(scope, request.receive, request._send)
