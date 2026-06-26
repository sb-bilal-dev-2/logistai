"""Test fixtures.

Points the app at an isolated temporary SQLite database BEFORE any app module
is imported, enables SQLite FK enforcement, builds the schema once, and hands
each test a clean session.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# --- isolate the DB before app.config is imported ----------------------------
_TMP_DB = Path(tempfile.gettempdir()) / "logistai_test.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ.setdefault("SEED_TRUCK_COUNT", "30")
# Tests run deterministically offline: no LLM calls unless a test explicitly
# opts in by overriding settings. (The app default is LLM_PROVIDER=ollama.)
os.environ["LLM_PROVIDER"] = "none"
os.environ.pop("USE_LLM_RERANK", None)

from sqlalchemy import event, inspect  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app import models  # noqa: E402,F401


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _rec):  # noqa: ANN001
    """SQLite ignores FOREIGN KEY constraints unless this pragma is set."""
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session():
    """A clean session; every table is emptied before the test runs."""
    from app.database import SessionLocal

    s = SessionLocal()
    # Delete children first to respect FKs.
    for table in reversed(Base.metadata.sorted_tables):
        s.execute(table.delete())
    s.commit()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def inspector():
    return inspect(engine)
