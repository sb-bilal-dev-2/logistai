"""Request generator: volume guarantee, validity, agent wiring."""
from __future__ import annotations

import random

from app import generator
from app.config import settings
from app.models import AgentTaklifi, Zapros


def test_generate_once_creates_batch_and_matches(session):
    # Need trucks for matching to produce logs.
    from app.seed import seed_trucks

    seed_trucks(count=10, force=True)
    ids = generator.generate_once(random.Random(1), run_agent=True)
    assert len(ids) == generator.BATCH
    assert session.query(Zapros).count() == generator.BATCH
    # Each created request got at least one recommendation.
    for zid in ids:
        assert session.query(AgentTaklifi).filter_by(zapros_id=zid).count() >= 1


def test_generate_pickup_differs_from_dropoff(session):
    rng = random.Random(7)
    for _ in range(50):
        z = generator._new_request(rng)
        assert z.yuk_ortish_joyi != z.yuk_tushirish_joyi


def test_daily_volume_floor_guaranteed():
    # Worst case = slowest interval. ticks/day * BATCH must clear 400.
    max_interval = settings.request_max_interval_s
    ticks_per_day = 86_400 // max_interval
    assert ticks_per_day * generator.BATCH >= 400


def test_interval_within_configured_window():
    rng = random.Random(3)
    for _ in range(100):
        s = generator.next_interval_seconds(rng)
        assert settings.request_min_interval_s <= s <= settings.request_max_interval_s
