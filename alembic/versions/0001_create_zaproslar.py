"""create zaproslar (freight requests) table

Revision ID: 0001
Revises:
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zaproslar",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("yuk_ortish_joyi", sa.String(length=255), nullable=False),
        sa.Column("yuk_tushirish_joyi", sa.String(length=255), nullable=False),
        sa.Column("yuklash_sanasi", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_zaproslar_created_at", "zaproslar", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_zaproslar_created_at", table_name="zaproslar")
    op.drop_table("zaproslar")
