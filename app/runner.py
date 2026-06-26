"""Orchestrator: seed -> backfill pending -> live generate+match loop.

Usage:
    python -m app.runner            # run the live system (Ctrl+C to stop)
    python -m app.runner --once     # one generate+match tick, then exit
"""
from __future__ import annotations

import argparse
import random
import re
import signal
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

from app import __version__
from app.analytics import print_summary
from app.config import settings
from app.database import engine, get_session
from app.generator import BATCH, generate_once, next_interval_seconds
from app.matching_agent import process_pending
from app.models import AgentTaklifi, Malumot, Zapros
from app.seed import seed_trucks


def _redact_url(url: str) -> str:
    """Show host/db without leaking any password in the connection string."""
    url = re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:***@", url)
    if url.startswith("sqlite"):
        return url.split("///")[-1] or url  # just the file path
    return url


def _estimated_daily_requests() -> int:
    avg_interval = (settings.request_min_interval_s + settings.request_max_interval_s) / 2
    if avg_interval <= 0:
        return 0
    return round(86_400 / avg_interval * BATCH)


def _startup_banner() -> None:
    with get_session() as s:
        n_zap = s.execute(select(func.count(Zapros.id))).scalar_one()
        n_mal = s.execute(select(func.count(Malumot.id))).scalar_one()
        n_tak = s.execute(select(func.count(AgentTaklifi.id))).scalar_one()

    line = "=" * 64
    print(line)
    print(f" LogistAI runner v{__version__}")
    print(line)
    print(f" Database     : {engine.dialect.name}  ->  {_redact_url(settings.database_url)}")
    print(f" Tables       : zaproslar={n_zap}  malumotlar={n_mal}  agent_takliflari={n_tak}")
    print(
        f" Generator    : every {settings.request_min_interval_s}-"
        f"{settings.request_max_interval_s}s, batch={BATCH}  "
        f"(~{_estimated_daily_requests()} requests/day, floor 400)"
    )
    print(
        f" Matching     : geo haversine, top-{settings.match_top_n}, "
        f"<= {settings.match_max_distance_km:.0f} km"
    )
    watcher = f"every {settings.watch_interval_s}s" if settings.watch_interval_s > 0 else "disabled"
    print(f" Watcher      : {watcher} (matches externally-created requests)")
    llm_line = settings.llm_label
    if settings.llm_provider in ("ollama", "vllm"):
        from app.llm import llm_reachable

        llm_line += "  [reachable]" if llm_reachable() else "  [unreachable -> geo fallback]"
    print(f" LLM re-rank  : {llm_line}")
    print(line)


def _bootstrap() -> None:
    """Ensure a fleet exists and nothing is left unmatched, with clear logs."""
    inserted = seed_trucks()
    if inserted:
        print(f"[seed] inserted {inserted} trucks into malumotlar")
    else:
        with get_session() as s:
            have = s.execute(select(func.count(Malumot.id))).scalar_one()
        print(f"[seed] fleet already present: {have} trucks (skipped seeding)")

    with get_session() as session:
        done = process_pending(session)
        if done:
            print(f"[backfill] matched {done} previously-unmatched request(s) on startup")
        else:
            print("[backfill] no pending requests - all caught up")


def _describe_matches(ids: list[int]) -> None:
    """Log, per created request, the pickup and the agent's top pick."""
    if not ids:
        return
    with get_session() as s:
        for zid in ids:
            z = s.get(Zapros, zid)
            top = s.execute(
                select(AgentTaklifi)
                .where(AgentTaklifi.zapros_id == zid, AgentTaklifi.reyting == 1)
            ).scalars().first()
            if top is None:
                print(f"  zapros #{zid:<4} {z.yuk_ortish_joyi:>12} -> (no truck matched)")
                continue
            truck = s.get(Malumot, top.mashina_id)
            dist = f"{top.masofa_km:.0f} km" if top.masofa_km is not None else "n/a"
            # Show whether the LLM re-ranked this match or it used geo order.
            # (izoh is only set when the LLM returned a result; absent => fallback.)
            source = ""
            if settings.llm_enabled:
                source = " via LLM" if top.izoh else " via geo (LLM fallback)"
            print(
                f"  zapros #{zid:<4} {z.yuk_ortish_joyi:>12}  ->  "
                f"{truck.mashina_raqami:<11} @ {truck.joriy_lokatsiya:<16} "
                f"({dist}, {top.latency_ms:.0f} ms){source}"
            )


def run_live() -> None:
    _startup_banner()
    _bootstrap()
    rng = random.Random()
    scheduler = BackgroundScheduler(timezone="UTC")

    def tick() -> None:
        ids = generate_once(rng, run_agent=True)
        print(f"[tick] created + matched {len(ids)} request(s): {ids}")
        _describe_matches(ids)
        # Reschedule with a fresh random 1-10 min gap.
        nxt = next_interval_seconds(rng)
        scheduler.reschedule_job("gen", trigger="interval", seconds=nxt)
        print(f"[tick] next batch in {nxt}s")

    def watch() -> None:
        # Catch any request created out-of-band (not by our generator) and
        # match it in near-real-time, not just on startup.
        with get_session() as s:
            n = process_pending(s)
        if n:
            print(f"[watch] matched {n} externally-created request(s)")

    first = next_interval_seconds(rng)
    scheduler.add_job(tick, "interval", seconds=first, id="gen")
    if settings.watch_interval_s > 0:
        scheduler.add_job(
            watch, "interval", seconds=settings.watch_interval_s, id="watch"
        )
    scheduler.start()
    print(f"[runner] live - first batch in {first}s. Ctrl+C to stop.")

    def shutdown(*_):  # noqa: ANN001
        print("\n[runner] shutting down...")
        scheduler.shutdown(wait=False)
        print_summary()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Block forever; the scheduler runs in a background thread.
    try:
        signal.pause() if hasattr(signal, "pause") else _busy_wait()
    except (KeyboardInterrupt, SystemExit):
        shutdown()


def _busy_wait() -> None:
    # Windows has no signal.pause(); block on a never-set event instead.
    import threading

    threading.Event().wait()


def run_once() -> None:
    _startup_banner()
    _bootstrap()
    ids = generate_once(random.Random(), run_agent=True)
    print(f"[once] created + matched {len(ids)} request(s): {ids}")
    _describe_matches(ids)
    print_summary()


def main() -> None:
    parser = argparse.ArgumentParser(description="LogistAI runner")
    parser.add_argument("--once", action="store_true", help="single tick then exit")
    args = parser.parse_args()
    if args.once:
        run_once()
    else:
        run_live()


if __name__ == "__main__":
    main()
