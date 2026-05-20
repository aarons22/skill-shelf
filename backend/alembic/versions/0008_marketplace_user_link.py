"""Link marketplaces to users via created_by_user_id

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        batch_op.drop_column("owner_name")
        batch_op.drop_column("owner_email")


def downgrade() -> None:
    with op.batch_alter_table("marketplaces") as batch_op:
        batch_op.drop_column("created_by_user_id")
        batch_op.add_column(sa.Column("owner_name", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("owner_email", sa.Text(), nullable=False, server_default=""))
