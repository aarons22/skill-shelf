"""Store OAuth client secret directly in auth_providers

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("auth_providers", sa.Column("client_secret", sa.Text(), nullable=False, server_default=""))
    op.drop_column("auth_providers", "client_secret_env_var")


def downgrade() -> None:
    op.add_column("auth_providers", sa.Column("client_secret_env_var", sa.Text(), nullable=False, server_default=""))
    op.drop_column("auth_providers", "client_secret")
