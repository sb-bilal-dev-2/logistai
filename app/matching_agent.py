"""The matching agent.

Given a freight request it:
  1. resolves the loading place (yuk_ortish_joyi) to coordinates,
  2. scores every truck by great-circle distance (closest first),
  3. optionally lets a local LLM (Ollama / vLLM) re-rank the shortlist,
  4. writes the top-N recommendations to `agent_takliflari`, recording the
     request-created time, the recommendation time, and the latency.

It is intentionally side-effect-contained: `recommend_for_request` does all DB
writes inside the caller-provided session and returns the created log rows.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.geo import GeoPoint, haversine_km, resolve_location
from app.llm import llm_rerank
from app.models import AgentTaklifi, Malumot, Zapros


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Candidate:
    mashina: Malumot
    point: Optional[GeoPoint]
    distance_km: Optional[float]


def _score_trucks(loading_place: str, trucks: list[Malumot]) -> list[Candidate]:
    """Rank trucks by distance to the loading place (None distance sinks last)."""
    origin = resolve_location(loading_place)
    cands: list[Candidate] = []
    for truck in trucks:
        pt = resolve_location(truck.joriy_lokatsiya)
        dist = (
            haversine_km(origin, pt) if origin is not None and pt is not None else None
        )
        cands.append(Candidate(mashina=truck, point=pt, distance_km=dist))

    # Sort: known distances ascending first, unknown distances last.
    cands.sort(key=lambda c: (c.distance_km is None, c.distance_km or 0.0))
    return cands


def recommend_for_request(session: Session, zapros: Zapros) -> list[AgentTaklifi]:
    """Produce + persist recommendations for one request. Returns the log rows."""
    started = time.perf_counter()

    trucks = list(session.execute(select(Malumot)).scalars())
    if not trucks:
        return []

    ranked = _score_trucks(zapros.yuk_ortish_joyi, trucks)

    # Keep candidates within the max-distance budget when distance is known;
    # always allow unknown-distance trucks as fallback so we never starve.
    within = [
        c for c in ranked
        if c.distance_km is None or c.distance_km <= settings.match_max_distance_km
    ]
    shortlist = (within or ranked)[: max(settings.match_top_n, 1)]

    # Optional LLM re-rank of the shortlist.
    order_ids = [c.mashina.id for c in shortlist]
    rationale_by_id: dict[int, str] = {}
    if settings.llm_enabled and len(shortlist) > 1:
        payload = [
            {
                "mashina_id": c.mashina.id,
                "mashina_raqami": c.mashina.mashina_raqami,
                "lokatsiya": c.mashina.joriy_lokatsiya,
                "masofa_km": round(c.distance_km, 1) if c.distance_km is not None else None,
            }
            for c in shortlist
        ]
        result = llm_rerank(zapros.yuk_ortish_joyi, payload)
        if result:
            valid = [i for i in result["order"] if i in order_ids]
            if valid:
                # Preserve any ids the LLM dropped, appended in original order.
                order_ids = valid + [i for i in order_ids if i not in valid]
            rationale = result.get("rationale")
            if rationale and order_ids:
                rationale_by_id[order_ids[0]] = str(rationale)[:512]

    by_id = {c.mashina.id: c for c in shortlist}
    finished_at = _utcnow()
    latency_ms = (time.perf_counter() - started) * 1000.0

    logs: list[AgentTaklifi] = []
    for rank, mashina_id in enumerate(order_ids, start=1):
        cand = by_id[mashina_id]
        log = AgentTaklifi(
            zapros_id=zapros.id,
            mashina_id=mashina_id,
            zapros_yaratilgan_vaqti=zapros.created_at,
            agent_taklif_bergan_vaqti=finished_at,
            reyting=rank,
            masofa_km=round(cand.distance_km, 2) if cand.distance_km is not None else None,
            latency_ms=round(latency_ms, 2),
            izoh=rationale_by_id.get(mashina_id),
        )
        session.add(log)
        logs.append(log)

    session.commit()
    return logs


def process_pending(session: Session, limit: int = 500) -> int:
    """Find requests that have no recommendation yet and process them.

    This is the agent's *watcher* path: it matches any request that wasn't
    matched synchronously at creation — e.g. created out-of-band by another
    service, or inserted while the agent was down. Called once on startup
    (backfill) and then continuously by the background watcher.

    Rows are claimed with ``FOR UPDATE SKIP LOCKED`` so multiple agent workers
    can share one backlog without double-matching the same request. On
    PostgreSQL this is real row-level locking; on SQLite (no row locks) the
    clause is simply not emitted, which is fine for a single worker.
    """
    already = select(AgentTaklifi.zapros_id).distinct().subquery()
    pending = list(
        session.execute(
            select(Zapros)
            .where(Zapros.id.not_in(select(already.c.zapros_id)))
            .order_by(Zapros.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    for zapros in pending:
        recommend_for_request(session, zapros)
    return len(pending)
