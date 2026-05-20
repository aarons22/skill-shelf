from fastapi import HTTPException, status
from sqlalchemy import select, update

from app.lib.auth import DEFAULT_ORGANIZATION_ID, now_ts
from app.models import organizations


def is_required(conn) -> bool:
    row = conn.execute(
        select(organizations.c.bootstrap_completed_at).where(organizations.c.id == DEFAULT_ORGANIZATION_ID)
    ).one_or_none()
    return row is None or row[0] is None


def mark_completed(conn) -> int:
    completed_at = now_ts()
    result = conn.execute(
        update(organizations)
        .where(
            organizations.c.id == DEFAULT_ORGANIZATION_ID,
            organizations.c.bootstrap_completed_at.is_(None),
        )
        .values(bootstrap_completed_at=completed_at, updated_at=completed_at)
    )
    if result.rowcount != 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Setup already complete")
    return completed_at
