"""Seed the `malumotlar` table with a fleet of trucks.

Locations are a mix of known city names and raw GPS pairs so the geo-resolver
gets exercised on both input shapes.
"""
from __future__ import annotations

import random

from sqlalchemy import func, select

from app.config import settings
from app.database import get_session
from app.geo import GAZETTEER, known_locations
from app.models import Malumot

_REGION_LETTERS = ["01", "10", "20", "25", "30", "40", "50", "60", "70", "80", "85", "90", "95"]


def _random_plate(rng: random.Random) -> str:
    region = rng.choice(_REGION_LETTERS)
    letters = "".join(rng.choice("ABCEHKMOPTXY") for _ in range(1))
    nums = f"{rng.randint(0, 999):03d}"
    tail = "".join(rng.choice("ABCEHKMOPTXY") for _ in range(2))
    return f"{region} {letters}{nums}{tail}"


def _random_location(rng: random.Random) -> str:
    # 70% named place, 30% jittered GPS near a known place.
    if rng.random() < 0.7:
        return rng.choice(known_locations())
    base = rng.choice(list(GAZETTEER.values()))
    lat = base.lat + rng.uniform(-0.4, 0.4)
    lon = base.lon + rng.uniform(-0.4, 0.4)
    return f"{lat:.4f},{lon:.4f}"


def seed_trucks(count: int | None = None, *, force: bool = False) -> int:
    """Insert `count` trucks if the table is empty (or `force=True`). Returns inserted."""
    count = count or settings.seed_truck_count
    rng = random.Random(42)  # deterministic fleet for reproducible demos
    with get_session() as session:
        existing = session.execute(select(func.count(Malumot.id))).scalar_one()
        if existing and not force:
            return 0
        trucks = [
            Malumot(
                mashina_raqami=_random_plate(rng),
                joriy_lokatsiya=_random_location(rng),
            )
            for _ in range(count)
        ]
        session.add_all(trucks)
        session.commit()
        return len(trucks)


if __name__ == "__main__":
    inserted = seed_trucks()
    print(f"Seeded {inserted} trucks into malumotlar.")
