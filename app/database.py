"""SQLAlchemy engine / session setup."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# `future=True` engine, pre-ping to survive idle connections on Postgres.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_session():
    """Context-manager friendly session factory."""
    return SessionLocal()
