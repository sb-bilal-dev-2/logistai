"""Schema-level guarantees: NOT NULL, FK enforcement, defaults, indexes, PK."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import AgentTaklifi, Malumot, Zapros


def _utc():
    return datetime.now(timezone.utc)


# --- NOT NULL constraints ----------------------------------------------------
def test_zapros_requires_pickup(session):
    z = Zapros(
        yuk_ortish_joyi=None,
        yuk_tushirish_joyi="Samarqand",
        yuklash_sanasi=_utc(),
    )
    session.add(z)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_zapros_requires_dropoff_and_date(session):
    session.add(Zapros(yuk_ortish_joyi="Toshkent", yuk_tushirish_joyi=None, yuklash_sanasi=_utc()))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_malumot_requires_plate_and_location(session):
    session.add(Malumot(mashina_raqami=None, joriy_lokatsiya="Toshkent"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# --- Foreign keys ------------------------------------------------------------
def test_agent_taklifi_fk_enforced(session):
    # zapros_id / mashina_id pointing nowhere must be rejected.
    bad = AgentTaklifi(
        zapros_id=99999,
        mashina_id=88888,
        zapros_yaratilgan_vaqti=_utc(),
        agent_taklif_bergan_vaqti=_utc(),
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_agent_taklifi_valid_fk_ok(session):
    z = Zapros(yuk_ortish_joyi="Toshkent", yuk_tushirish_joyi="Nukus", yuklash_sanasi=_utc())
    m = Malumot(mashina_raqami="01 A001AA", joriy_lokatsiya="Toshkent")
    session.add_all([z, m])
    session.commit()
    session.add(
        AgentTaklifi(
            zapros_id=z.id,
            mashina_id=m.id,
            zapros_yaratilgan_vaqti=z.created_at,
            agent_taklif_bergan_vaqti=_utc(),
        )
    )
    session.commit()  # should not raise
    assert session.query(AgentTaklifi).count() == 1


# --- Defaults / timestamps ---------------------------------------------------
def test_timestamps_autopopulate(session):
    z = Zapros(yuk_ortish_joyi="Toshkent", yuk_tushirish_joyi="Buxoro", yuklash_sanasi=_utc())
    session.add(z)
    session.commit()
    assert z.created_at is not None
    assert z.updated_at is not None


def test_reyting_defaults_to_one(session):
    z = Zapros(yuk_ortish_joyi="Toshkent", yuk_tushirish_joyi="Nukus", yuklash_sanasi=_utc())
    m = Malumot(mashina_raqami="01 A002AA", joriy_lokatsiya="Toshkent")
    session.add_all([z, m])
    session.commit()
    t = AgentTaklifi(
        zapros_id=z.id,
        mashina_id=m.id,
        zapros_yaratilgan_vaqti=z.created_at,
        agent_taklif_bergan_vaqti=_utc(),
    )
    session.add(t)
    session.commit()
    assert t.reyting == 1
    # Optional analytics fields may legitimately be NULL.
    assert t.izoh is None


# --- PK autoincrement --------------------------------------------------------
def test_pk_autoincrements(session):
    a = Malumot(mashina_raqami="01 A003AA", joriy_lokatsiya="Toshkent")
    b = Malumot(mashina_raqami="01 A004AA", joriy_lokatsiya="Nukus")
    session.add_all([a, b])
    session.commit()
    assert a.id is not None and b.id is not None and a.id != b.id


# --- Indexes -----------------------------------------------------------------
def test_expected_indexes_exist(inspector):
    tak_idx = {i["name"] for i in inspector.get_indexes("agent_takliflari")}
    assert "ix_agent_takliflari_zapros_id" in tak_idx
    assert "ix_agent_takliflari_mashina_id" in tak_idx
    assert "ix_agent_takliflari_zapros_reyting" in tak_idx

    mal_idx = {i["name"] for i in inspector.get_indexes("malumotlar")}
    assert "ix_malumotlar_mashina_raqami" in mal_idx


def test_fk_columns_indexed_for_join_perf(inspector):
    # Both FK columns should be covered by an index to keep joins/lookups cheap.
    indexes = inspector.get_indexes("agent_takliflari")
    covered = {col for idx in indexes for col in idx["column_names"]}
    assert "zapros_id" in covered
    assert "mashina_id" in covered
