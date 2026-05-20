"""Rename legacy workspace tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-20
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("workspace_settings", "organization_settings")
    op.rename_table("workspace_role_grants", "organization_role_grants")
    op.execute("UPDATE organization_role_grants SET role = 'organization_admin' WHERE role = 'workspace_admin'")


def downgrade() -> None:
    op.execute("UPDATE organization_role_grants SET role = 'workspace_admin' WHERE role = 'organization_admin'")
    op.rename_table("organization_role_grants", "workspace_role_grants")
    op.rename_table("organization_settings", "workspace_settings")
