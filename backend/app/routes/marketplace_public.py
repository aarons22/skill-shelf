"""
Public marketplace.json endpoint.

Regenerated from DB on every request — the DB is the source of truth.
The committed marketplace.json in the repo is for `git clone` consumers.
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db import get_connection
from app.lib.auth import public_read_dependencies, require_marketplace_read
from app.lib.marketplace_json import build_marketplace_json
from app.models import marketplaces
from sqlalchemy import select

router = APIRouter(tags=["public"], dependencies=[Depends(public_read_dependencies)])


def _get_marketplace_json(slug: str, request: Request) -> dict:
    with get_connection() as conn:
        exists = conn.execute(
            select(marketplaces.c.slug).where(marketplaces.c.slug == slug)
        ).one_or_none()
        if exists is None:
            raise HTTPException(status_code=404, detail="Marketplace not found")
        require_marketplace_read(
            conn,
            getattr(request.state, "actor", None),
            slug,
            getattr(request.state, "read_token", None),
        )
        return build_marketplace_json(slug, conn)


@router.get("/m/{slug}")
def get_marketplace_json(slug: str, request: Request):
    return JSONResponse(content=_get_marketplace_json(slug, request))


@router.get("/m/{slug}/marketplace.json")
def get_marketplace_json_explicit(slug: str, request: Request):
    return JSONResponse(content=_get_marketplace_json(slug, request))
