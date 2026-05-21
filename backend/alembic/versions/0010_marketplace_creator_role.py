"""Replace marketplace_creation setting with marketplace_creator org role

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-21

Backfill: if the old marketplace_creation setting was "authenticated", grant
marketplace_creator to every existing user so they retain creation access.
If it was "organization_admin", org admins still have implicit create access
and no grants are needed.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    settings = conn.execute(
        sa.text("SELECT marketplace_creation FROM organization_settings WHERE id = 1")
    ).one_or_none()

    if settings and settings[0] == "authenticated":
        import time
        now = int(time.time())
        users = conn.execute(
            sa.text("SELECT id FROM users WHERE organization_id = 1 AND disabled_at IS NULL")
        ).all()
        for (user_id,) in users:
            exists = conn.execute(
                sa.text(
                    "SELECT 1 FROM organization_role_grants "
                    "WHERE organization_id = 1 AND principal_type = 'user' "
                    "AND principal_id = :uid AND role = 'marketplace_creator'"
                ),
                {"uid": user_id},
            ).one_or_none()
            if exists is None:
                conn.execute(
                    sa.text(
                        "INSERT INTO organization_role_grants "
                        "(organization_id, principal_type, principal_id, role, created_at) "
                        "VALUES (1, 'user', :uid, 'marketplace_creator', :now)"
                    ),
                    {"uid": user_id, "now": now},
                )

    op.drop_column("organization_settings", "marketplace_creation")


def downgrade() -> None:
    op.add_column(
        "organization_settings",
        sa.Column("marketplace_creation", sa.Text(), nullable=False, server_default="authenticated"),
    )
