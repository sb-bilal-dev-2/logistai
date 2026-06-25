"""create agent_takliflari (agent suggestion log) table

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_takliflari",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("zapros_id", sa.Integer(), nullable=False),
        sa.Column("mashina_id", sa.Integer(), nullable=False),
        sa.Column("zapros_yaratilgan_vaqti", sa.DateTime(timezone=True), nullable=False),
        sa.Column("agent_taklif_bergan_vaqti", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reyting", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("masofa_km", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("izoh", sa.String(length=512), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["zapros_id"], ["zaproslar.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["mashina_id"], ["malumotlar.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_agent_takliflari_zapros_id", "agent_takliflari", ["zapros_id"]
    )
    op.create_index(
        "ix_agent_takliflari_mashina_id", "agent_takliflari", ["mashina_id"]
    )
    op.create_index(
        "ix_agent_takliflari_zapros_reyting",
        "agent_takliflari",
        ["zapros_id", "reyting"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_takliflari_zapros_reyting", table_name="agent_takliflari")
    op.drop_index("ix_agent_takliflari_mashina_id", table_name="agent_takliflari")
    op.drop_index("ix_agent_takliflari_zapros_id", table_name="agent_takliflari")
    op.drop_table("agent_takliflari")
