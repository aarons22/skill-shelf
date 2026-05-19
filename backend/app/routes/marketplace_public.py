"""
Public marketplace.json endpoint.

Regenerated from DB on every request — the DB is the source of truth.
The committed marketplace.json in the repo is for `git clone` consumers.
"""
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.db import get_connection
from app.lib.marketplace_json import build_marketplace_json
from app.models import marketplaces
from sqlalchemy import select

router = APIRouter(tags=["public"])


def _get_marketplace_json(slug: str) -> dict:
    with get_connection() as conn:
        exists = conn.execute(
            select(marketplaces.c.slug).where(marketplaces.c.slug == slug)
        ).one_or_none()
        if exists is None:
            raise HTTPException(status_code=404, detail="Marketplace not found")
        return build_marketplace_json(slug, conn)


@router.get("/m/{slug}")
def get_marketplace_json(slug: str):
    return JSONResponse(content=_get_marketplace_json(slug))


@router.get("/m/{slug}/marketplace.json")
def get_marketplace_json_explicit(slug: str):
    return JSONResponse(content=_get_marketplace_json(slug))
