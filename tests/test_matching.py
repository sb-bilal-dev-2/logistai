"""Matching-agent behaviour: correct ranking, limits, latency, no-crash paths."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app import matching_agent
from app.config import settings
from app.models import AgentTaklifi, Malumot, Zapros


def _make_request(session, pickup="Toshkent", drop="Samarqand"):
    z = Zapros(
        yuk_ortish_joyi=pickup,
        yuk_tushirish_joyi=drop,
        yuklash_sanasi=datetime.now(timezone.utc),
    )
    session.add(z)
    session.commit()
    return z


def _add_trucks(session, locations):
    trucks = [
        Malumot(mashina_raqami=f"01 A{i:03d}AA", joriy_lokatsiya=loc)
        for i, loc in enumerate(locations)
    ]
    session.add_all(trucks)
    session.commit()
    return trucks


def test_ranking_is_nearest_first(session):
    _add_trucks(session, ["Termiz", "Samarqand", "Toshkent", "Nukus"])
    z = _make_request(session, pickup="Toshkent")
    logs = matching_agent.recommend_for_request(session, z)
    assert logs, "agent must produce at least one recommendation"
    # reyting 1 must be the closest (Toshkent itself -> distance ~0).
    top = next(l for l in logs if l.reyting == 1)
    assert top.masofa_km == pytest.approx(0.0, abs=1.0)
    # distances must be non-decreasing with rank.
    by_rank = sorted(logs, key=lambda l: l.reyting)
    dists = [l.masofa_km for l in by_rank]
    assert dists == sorted(dists)


def test_respects_top_n(session):
    _add_trucks(session, ["Toshkent", "Samarqand", "Buxoro", "Nukus", "Andijon"])
    z = _make_request(session)
    logs = matching_agent.recommend_for_request(session, z)
    assert len(logs) <= settings.match_top_n


def test_latency_and_timestamps_recorded(session):
    _add_trucks(session, ["Toshkent"])
    z = _make_request(session)
    logs = matching_agent.recommend_for_request(session, z)
    log = logs[0]
    assert log.latency_ms is not None and log.latency_ms >= 0
    assert log.zapros_yaratilgan_vaqti is not None
    assert log.agent_taklif_bergan_vaqti is not None
    # recommendation must not predate the request.
    assert log.agent_taklif_bergan_vaqti >= log.zapros_yaratilgan_vaqti


def test_no_trucks_returns_empty_no_crash(session):
    z = _make_request(session)
    assert matching_agent.recommend_for_request(session, z) == []


def test_unresolvable_truck_location_does_not_crash(session):
    # All trucks have unknown locations -> distances are None, agent still picks.
    _add_trucks(session, ["Atlantis", "Nowhere", "???"])
    z = _make_request(session)
    logs = matching_agent.recommend_for_request(session, z)
    assert logs, "agent must still recommend when distances are unknown"
    assert all(l.masofa_km is None for l in logs)


def test_max_distance_filter(session):
    # Only a far truck (Nukus, >1000km from Termiz) and one near.
    _add_trucks(session, ["Termiz", "Nukus"])
    z = _make_request(session, pickup="Termiz")
    logs = matching_agent.recommend_for_request(session, z)
    # The near truck (Termiz, 0km) must be ranked first.
    assert min(logs, key=lambda l: l.reyting).masofa_km == pytest.approx(0.0, abs=1.0)


def test_agent_applies_llm_rerank_when_enabled(session, monkeypatch):
    from app.config import Settings

    # Enable a (mocked) local-LLM provider and force a reversed ordering.
    monkeypatch.setattr(matching_agent, "settings", Settings(llm_provider="ollama"))

    def fake_rerank(place, cands):
        ids = [c["mashina_id"] for c in cands]
        return {"order": list(reversed(ids)), "rationale": "llm says so"}

    monkeypatch.setattr(matching_agent, "llm_rerank", fake_rerank)

    _add_trucks(session, ["Toshkent", "Samarqand", "Buxoro"])
    z = _make_request(session, pickup="Toshkent")
    logs = matching_agent.recommend_for_request(session, z)

    # Geo order would be Toshkent(0km) first; the LLM reversed it, so the
    # top-ranked log must NOT be the 0km truck, and rationale is recorded.
    top = next(l for l in logs if l.reyting == 1)
    assert top.masofa_km != 0.0
    assert top.izoh == "llm says so"


def test_geo_fallback_when_llm_returns_none(session, monkeypatch):
    from app.config import Settings

    monkeypatch.setattr(matching_agent, "settings", Settings(llm_provider="ollama"))
    monkeypatch.setattr(matching_agent, "llm_rerank", lambda place, cands: None)

    _add_trucks(session, ["Samarqand", "Toshkent", "Nukus"])
    z = _make_request(session, pickup="Toshkent")
    logs = matching_agent.recommend_for_request(session, z)
    # LLM failed -> deterministic geo order stands (nearest first).
    top = next(l for l in logs if l.reyting == 1)
    assert top.masofa_km == pytest.approx(0.0, abs=1.0)


def test_process_pending_is_idempotent(session):
    _add_trucks(session, ["Toshkent", "Samarqand"])
    _make_request(session)
    _make_request(session)
    first = matching_agent.process_pending(session)
    assert first == 2
    # Second run: nothing left to match.
    assert matching_agent.process_pending(session) == 0
    # Exactly the two requests are matched, no duplicates.
    distinct = {l.zapros_id for l in session.query(AgentTaklifi).all()}
    assert len(distinct) == 2
