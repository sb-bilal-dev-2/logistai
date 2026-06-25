"""Central configuration, loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root if present.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///logistai.db")

    request_min_interval_s: int = _int("REQUEST_MIN_INTERVAL_SECONDS", 60)
    request_max_interval_s: int = _int("REQUEST_MAX_INTERVAL_SECONDS", 600)

    match_top_n: int = _int("MATCH_TOP_N", 3)
    match_max_distance_km: float = float(_int("MATCH_MAX_DISTANCE_KM", 600))

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "claude-opus-4-8")
    use_llm_rerank: bool = _bool("USE_LLM_RERANK", False)

    seed_truck_count: int = _int("SEED_TRUCK_COUNT", 120)

    @property
    def llm_enabled(self) -> bool:
        return self.use_llm_rerank and bool(self.anthropic_api_key)


settings = Settings()
