"""Agent-performance analytics over `agent_takliflari`."""
from __future__ import annotations

from sqlalchemy import func, select

from app.database import get_session
from app.models import AgentTaklifi, Malumot, Zapros


def summary() -> dict:
    with get_session() as session:
        n_requests = session.execute(select(func.count(Zapros.id))).scalar_one()
        n_trucks = session.execute(select(func.count(Malumot.id))).scalar_one()
        n_logs = session.execute(select(func.count(AgentTaklifi.id))).scalar_one()
        n_matched = session.execute(
            select(func.count(func.distinct(AgentTaklifi.zapros_id)))
        ).scalar_one()

        avg_latency = session.execute(
            select(func.avg(AgentTaklifi.latency_ms))
        ).scalar_one()
        max_latency = session.execute(
            select(func.max(AgentTaklifi.latency_ms))
        ).scalar_one()
        avg_dist = session.execute(
            select(func.avg(AgentTaklifi.masofa_km)).where(AgentTaklifi.reyting == 1)
        ).scalar_one()

        return {
            "zaproslar": n_requests,
            "malumotlar": n_trucks,
            "takliflar_log": n_logs,
            "matched_requests": n_matched,
            "unmatched_requests": n_requests - n_matched,
            "avg_latency_ms": round(avg_latency, 2) if avg_latency is not None else None,
            "max_latency_ms": round(max_latency, 2) if max_latency is not None else None,
            "avg_top1_distance_km": round(avg_dist, 1) if avg_dist is not None else None,
        }


def print_summary() -> None:
    s = summary()
    print("=== LogistAI agent analytics ===")
    for k, v in s.items():
        print(f"  {k:24}: {v}")


if __name__ == "__main__":
    print_summary()
