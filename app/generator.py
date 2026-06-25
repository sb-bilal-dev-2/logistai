"""Automatic freight-request generator.

Creates `zaproslar` rows at a random 1-10 minute interval. The task requires
>=400 requests/day; the default 60-600s window averages ~5.5 min/request, i.e.
~261/day. To guarantee the >=400/day floor we generate a small *batch* of
requests on each tick (BATCH), so the daily rate clears the requirement with
margin while still feeling like a live stream.

Run standalone for a blocking scheduler, or call `generate_once()` from the
orchestrator.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import get_session
from app.geo import known_locations
from app.matching_agent import recommend_for_request
from app.models import Zapros

# Requests created per tick. The required floor is >=400 requests/day. The
# slowest case is the max interval (600s) -> 86400/600 = 144 ticks/day, so we
# need BATCH >= 3 to guarantee 144*3 = 432 >= 400 even then. With the average
# interval (~330s) this yields ~785/day, comfortably above the floor.
BATCH = 3


def _new_request(rng: random.Random) -> Zapros:
    places = known_locations()
    ortish = rng.choice(places)
    tushirish = rng.choice([p for p in places if p != ortish])
    # Pickup date: today..+3 days ahead.
    yuklash = datetime.now(timezone.utc) + timedelta(
        days=rng.randint(0, 3), hours=rng.randint(0, 23)
    )
    return Zapros(
        yuk_ortish_joyi=ortish,
        yuk_tushirish_joyi=tushirish,
        yuklash_sanasi=yuklash,
    )


def generate_once(rng: random.Random | None = None, *, run_agent: bool = True) -> list[int]:
    """Create a batch of requests and (optionally) immediately match them.

    Returns the list of created request ids.
    """
    rng = rng or random.Random()
    created_ids: list[int] = []
    with get_session() as session:
        for _ in range(BATCH):
            zapros = _new_request(rng)
            session.add(zapros)
            session.commit()
            created_ids.append(zapros.id)
            if run_agent:
                recommend_for_request(session, zapros)
    return created_ids


def next_interval_seconds(rng: random.Random) -> int:
    return rng.randint(settings.request_min_interval_s, settings.request_max_interval_s)
