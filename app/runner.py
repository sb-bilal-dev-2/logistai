"""Orchestrator: seed -> backfill pending -> live generate+match loop.

Usage:
    python -m app.runner            # run the live system (Ctrl+C to stop)
    python -m app.runner --once     # one generate+match tick, then exit
"""
from __future__ import annotations

import argparse
import random
import signal
import sys

from apscheduler.schedulers.background import BackgroundScheduler

from app.analytics import print_summary
from app.config import settings
from app.database import get_session
from app.generator import generate_once, next_interval_seconds
from app.matching_agent import process_pending
from app.seed import seed_trucks


def _bootstrap() -> None:
    inserted = seed_trucks()
    if inserted:
        print(f"[seed] inserted {inserted} trucks into malumotlar")
    with get_session() as session:
        done = process_pending(session)
        if done:
            print(f"[backfill] matched {done} previously-unmatched requests")


def run_live() -> None:
    _bootstrap()
    rng = random.Random()
    scheduler = BackgroundScheduler(timezone="UTC")

    def tick() -> None:
        ids = generate_once(rng, run_agent=True)
        print(f"[tick] created+matched requests: {ids}")
        # Reschedule with a fresh random 1-10 min gap.
        scheduler.reschedule_job("gen", trigger="interval", seconds=next_interval_seconds(rng))

    scheduler.add_job(tick, "interval", seconds=next_interval_seconds(rng), id="gen")
    scheduler.start()
    print(
        f"[runner] live. interval {settings.request_min_interval_s}-"
        f"{settings.request_max_interval_s}s, LLM rerank={settings.llm_label}. "
        "Ctrl+C to stop."
    )

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
    _bootstrap()
    ids = generate_once(random.Random(), run_agent=True)
    print(f"[once] created+matched requests: {ids}")
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
