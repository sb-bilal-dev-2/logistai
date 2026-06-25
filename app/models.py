"""ORM models mirroring the three required tables.

Table / column names follow the task spec verbatim (Uzbek):
  - zaproslar          -> freight requests
  - malumotlar         -> trucks / vehicles
  - agent_takliflari   -> agent suggestion log
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Zapros(Base):
    """A freight-shipping request that the agent must fulfil."""

    __tablename__ = "zaproslar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    yuk_ortish_joyi: Mapped[str] = mapped_column(String(255), nullable=False)
    yuk_tushirish_joyi: Mapped[str] = mapped_column(String(255), nullable=False)
    yuklash_sanasi: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    takliflar: Mapped[list["AgentTaklifi"]] = relationship(back_populates="zapros")


class Malumot(Base):
    """A transport vehicle with its current location."""

    __tablename__ = "malumotlar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mashina_raqami: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Free-form location: "Toshkent", "Samarqand shahri", or "41.31,69.24".
    joriy_lokatsiya: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    takliflar: Mapped[list["AgentTaklifi"]] = relationship(back_populates="mashina")


class AgentTaklifi(Base):
    """One recommendation produced by the matching agent (with latency)."""

    __tablename__ = "agent_takliflari"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zapros_id: Mapped[int] = mapped_column(
        ForeignKey("zaproslar.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mashina_id: Mapped[int] = mapped_column(
        ForeignKey("malumotlar.id", ondelete="CASCADE"), nullable=False, index=True
    )

    zapros_yaratilgan_vaqti: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    agent_taklif_bergan_vaqti: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Extra observability fields (not strictly required, but cheap + useful).
    reyting: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    masofa_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    izoh: Mapped[str | None] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
        nullable=False,
    )

    zapros: Mapped["Zapros"] = relationship(back_populates="takliflar")
    mashina: Mapped["Malumot"] = relationship(back_populates="takliflar")


Index("ix_agent_takliflari_zapros_reyting", AgentTaklifi.zapros_id, AgentTaklifi.reyting)
