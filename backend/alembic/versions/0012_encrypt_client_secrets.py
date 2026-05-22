"""Encrypt auth_provider client secrets at rest.

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-22
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    from app.lib.secret_box import encrypt, is_encrypted

    rows = conn.execute(
        sa.text("SELECT id, client_secret FROM auth_providers WHERE client_secret != ''")
    ).fetchall()
    for row_id, secret in rows:
        if not is_encrypted(secret):
            conn.execute(
                sa.text("UPDATE auth_providers SET client_secret = :s WHERE id = :id"),
                {"s": encrypt(secret), "id": row_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    from app.lib.secret_box import decrypt, is_encrypted

    rows = conn.execute(
        sa.text("SELECT id, client_secret FROM auth_providers WHERE client_secret != ''")
    ).fetchall()
    for row_id, secret in rows:
        if is_encrypted(secret):
            conn.execute(
                sa.text("UPDATE auth_providers SET client_secret = :s WHERE id = :id"),
                {"s": decrypt(secret), "id": row_id},
            )
