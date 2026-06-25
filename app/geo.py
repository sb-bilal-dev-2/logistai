"""Geo utilities: Uzbekistan gazetteer, location resolution, haversine distance.

The matching agent has to compare a request's *yuk_ortish_joyi* (loading place)
against each truck's *joriy_lokatsiya*. Both can be:
  * a known region / city name (possibly in Latin or Cyrillic, with suffixes
    like "shahri" / "viloyati"), or
  * a raw GPS pair  "41.31,69.24".

`resolve_location` turns any of those into (lat, lon); `haversine_km` measures
the great-circle distance between two such points.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import NamedTuple, Optional


class GeoPoint(NamedTuple):
    lat: float
    lon: float


# --- Uzbekistan gazetteer: regional centers + a few notable cities -----------
# (lat, lon) of the administrative center, good enough for proximity ranking.
GAZETTEER: dict[str, GeoPoint] = {
    "toshkent": GeoPoint(41.2995, 69.2401),
    "tashkent": GeoPoint(41.2995, 69.2401),
    "nukus": GeoPoint(42.4531, 59.6103),
    "andijon": GeoPoint(40.7821, 72.3442),
    "andijan": GeoPoint(40.7821, 72.3442),
    "buxoro": GeoPoint(39.7680, 64.4210),
    "bukhara": GeoPoint(39.7680, 64.4210),
    "fargona": GeoPoint(40.3864, 71.7864),
    "fergana": GeoPoint(40.3864, 71.7864),
    "jizzax": GeoPoint(40.1158, 67.8422),
    "jizzakh": GeoPoint(40.1158, 67.8422),
    "namangan": GeoPoint(40.9983, 71.6726),
    "navoiy": GeoPoint(40.1033, 65.3739),
    "navoi": GeoPoint(40.1033, 65.3739),
    "qarshi": GeoPoint(38.8606, 65.7891),
    "karshi": GeoPoint(38.8606, 65.7891),
    "samarqand": GeoPoint(39.6542, 66.9597),
    "samarkand": GeoPoint(39.6542, 66.9597),
    "termiz": GeoPoint(37.2242, 67.2783),
    "termez": GeoPoint(37.2242, 67.2783),
    "guliston": GeoPoint(40.4897, 68.7842),
    "gulistan": GeoPoint(40.4897, 68.7842),
    "urganch": GeoPoint(41.5500, 60.6333),
    "urgench": GeoPoint(41.5500, 60.6333),
    "xiva": GeoPoint(41.3783, 60.3639),
    "khiva": GeoPoint(41.3783, 60.3639),
    "kokand": GeoPoint(40.5283, 70.9425),
    "qoqon": GeoPoint(40.5283, 70.9425),
    "angren": GeoPoint(41.0167, 70.1436),
    "chirchiq": GeoPoint(41.4689, 69.5828),
    "olmaliq": GeoPoint(40.8444, 69.5983),
    "bekobod": GeoPoint(40.2206, 69.2697),
    "shahrisabz": GeoPoint(39.0578, 66.8336),
    "denov": GeoPoint(38.2772, 67.8939),
    "zarafshon": GeoPoint(41.5872, 64.2056),
}

# Cyrillic -> Latin transliteration so "Тошкент" resolves like "Toshkent".
_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "",
    "ь": "", "ы": "i", "э": "e", "ю": "yu", "я": "ya", "қ": "q", "ғ": "g",
    "ҳ": "h", "ў": "o", "ё": "yo",
}

# Administrative noise words to strip before matching the gazetteer.
_NOISE = re.compile(
    r"\b(shahri|shahar|sh|viloyati|viloyat|tumani|tuman|city|region|obl|oblast)\b",
    re.IGNORECASE,
)

_GPS_RE = re.compile(
    r"^\s*(-?\d{1,3}(?:\.\d+)?)\s*[,;/ ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$"
)


def _translit(text: str) -> str:
    return "".join(_CYR_TO_LAT.get(ch, ch) for ch in text)


def normalize_name(raw: str) -> str:
    """Lowercase, transliterate, strip accents + admin noise words."""
    text = unicodedata.normalize("NFKC", raw or "").strip().lower()
    text = _translit(text)
    text = _NOISE.sub(" ", text)
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_gps(raw: str) -> Optional[GeoPoint]:
    """Parse 'lat,lon' style strings; return None if it isn't a GPS pair."""
    if not raw:
        return None
    m = _GPS_RE.match(raw)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if -90 <= lat <= 90 and -180 <= lon <= 180:
        return GeoPoint(lat, lon)
    return None


def resolve_location(raw: str) -> Optional[GeoPoint]:
    """Resolve a free-form location string to a GeoPoint, or None if unknown."""
    if not raw:
        return None
    gps = parse_gps(raw)
    if gps:
        return gps

    norm = normalize_name(raw)
    if not norm:
        return None

    # Exact match on the cleaned name.
    if norm in GAZETTEER:
        return GAZETTEER[norm]

    # Token / substring fallback: pick the first gazetteer key that appears
    # as a whole token in the normalized string.
    tokens = set(norm.split())
    for key, point in GAZETTEER.items():
        if key in tokens:
            return point
    for key, point in GAZETTEER.items():
        if key in norm:
            return point
    return None


def haversine_km(a: GeoPoint, b: GeoPoint) -> float:
    """Great-circle distance between two points in kilometers."""
    r = 6371.0088
    lat1, lon1, lat2, lon2 = map(math.radians, (a.lat, a.lon, b.lat, b.lon))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def known_locations() -> list[str]:
    """Canonical location labels used by the seeder / generator."""
    # One representative spelling per coordinate (skip duplicate aliases).
    seen: set[GeoPoint] = set()
    labels: list[str] = []
    preferred = {
        "toshkent": "Toshkent", "nukus": "Nukus", "andijon": "Andijon",
        "buxoro": "Buxoro", "fargona": "Fargona", "jizzax": "Jizzax",
        "namangan": "Namangan", "navoiy": "Navoiy", "qarshi": "Qarshi",
        "samarqand": "Samarqand", "termiz": "Termiz", "guliston": "Guliston",
        "urganch": "Urganch", "xiva": "Xiva", "qoqon": "Qoqon",
        "angren": "Angren", "chirchiq": "Chirchiq", "olmaliq": "Olmaliq",
        "bekobod": "Bekobod", "shahrisabz": "Shahrisabz", "denov": "Denov",
        "zarafshon": "Zarafshon",
    }
    for key, label in preferred.items():
        pt = GAZETTEER[key]
        if pt not in seen:
            seen.add(pt)
            labels.append(label)
    return labels
