"""create malumotlar (trucks) table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "malumotlar",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("mashina_raqami", sa.String(length=32), nullable=False),
        sa.Column("joriy_lokatsiya", sa.String(length=255), nullable=False),
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
    op.create_index("ix_malumotlar_mashina_raqami", "malumotlar", ["mashina_raqami"])


def downgrade() -> None:
    op.drop_index("ix_malumotlar_mashina_raqami", table_name="malumotlar")
    op.drop_table("malumotlar")
