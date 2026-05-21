"""Rename marketplace role strings to GitHub-style names

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-21

viewer              -> read
marketplace_contributor -> write
marketplace_maintainer  -> maintain
marketplace_admin       -> admin
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UPGRADES = [
    ("viewer", "read"),
    ("marketplace_contributor", "write"),
    ("marketplace_maintainer", "maintain"),
    ("marketplace_admin", "admin"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for old, new in _UPGRADES:
        conn.execute(
            sa.text("UPDATE marketplace_role_grants SET role = :new WHERE role = :old"),
            {"old": old, "new": new},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for old, new in _UPGRADES:
        conn.execute(
            sa.text("UPDATE marketplace_role_grants SET role = :old WHERE role = :new"),
            {"old": old, "new": new},
        )
