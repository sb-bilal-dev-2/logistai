"""Geo resolution / distance correctness + robustness against bad input."""
from __future__ import annotations

import math

import pytest

from app import geo


def test_parse_gps_valid():
    p = geo.parse_gps("41.31,69.24")
    assert p is not None
    assert p.lat == pytest.approx(41.31)
    assert p.lon == pytest.approx(69.24)


@pytest.mark.parametrize("bad", ["", "   ", "not a coord", "999,999", "41.31", None])
def test_parse_gps_rejects_garbage(bad):
    assert geo.parse_gps(bad) is None


def test_resolve_latin_and_suffix():
    assert geo.resolve_location("Samarqand viloyati") == geo.GAZETTEER["samarqand"]
    assert geo.resolve_location("Toshkent shahri") == geo.GAZETTEER["toshkent"]


def test_resolve_cyrillic():
    # "Тошкент" should transliterate to the Tashkent point.
    assert geo.resolve_location("Тошкент") == geo.GAZETTEER["toshkent"]


def test_resolve_gps_passthrough():
    p = geo.resolve_location("39.65,66.96")
    assert p is not None and p.lat == pytest.approx(39.65)


@pytest.mark.parametrize("bad", ["", None, "Atlantis", "12345"])
def test_resolve_unknown_returns_none(bad):
    assert geo.resolve_location(bad) is None


def test_haversine_known_distance():
    # Tashkent <-> Samarqand is ~265 km on the ground.
    d = geo.haversine_km(geo.GAZETTEER["toshkent"], geo.GAZETTEER["samarqand"])
    assert 250 < d < 285


def test_haversine_zero_for_same_point():
    p = geo.GAZETTEER["buxoro"]
    assert geo.haversine_km(p, p) == pytest.approx(0.0, abs=1e-9)


def test_haversine_symmetric():
    a, b = geo.GAZETTEER["nukus"], geo.GAZETTEER["andijon"]
    assert geo.haversine_km(a, b) == pytest.approx(geo.haversine_km(b, a))


def test_known_locations_unique_and_resolvable():
    labels = geo.known_locations()
    assert len(labels) == len(set(labels))  # no duplicate labels
    for label in labels:
        assert geo.resolve_location(label) is not None
