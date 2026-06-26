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


# Re-rank backend — LOCAL ONLY. By project requirement, no external ML/chatbot
# API may be used; every provider here runs on the local machine.
#   "none"   -> deterministic geo-ranker only (fully offline, no LLM)
#   "ollama" -> a locally-installed LLM served by Ollama on localhost (default)
#   "vllm"   -> a local vLLM server (high-throughput, GPU). Uses vLLM's
#               OpenAI-compatible /v1 API, so the same provider also works with
#               other local /v1 servers (llama.cpp, LM Studio, LocalAI) if you
#               point VLLM_BASE_URL at them. Fully offline.
_VALID_PROVIDERS = {"none", "ollama", "vllm"}


def _provider() -> str:
    p = os.getenv("LLM_PROVIDER", "").strip().lower()
    if p in _VALID_PROVIDERS:
        return p
    if p:
        # An unknown / disallowed provider (e.g. a cloud API) is rejected: this
        # project must not call any external ML/chatbot API. Fall through to the
        # local default rather than honoring it.
        pass
    # Default ON: re-rank via a local Ollama model (offline, no external API).
    # If the Ollama server isn't running, the agent transparently falls back to
    # the deterministic geo order, so this default never breaks a run.
    return "ollama"


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///logistai.db")

    request_min_interval_s: int = _int("REQUEST_MIN_INTERVAL_SECONDS", 60)
    request_max_interval_s: int = _int("REQUEST_MAX_INTERVAL_SECONDS", 600)

    match_top_n: int = _int("MATCH_TOP_N", 3)
    match_max_distance_km: float = float(_int("MATCH_MAX_DISTANCE_KM", 600))

    # How often the background watcher scans for unmatched requests (i.e. ones
    # created out-of-band, not by the in-process generator). 0 disables it.
    watch_interval_s: int = _int("WATCH_INTERVAL_SECONDS", 10)

    # --- re-rank LLM layer (optional, off by default) ---
    llm_provider: str = _provider()

    # Local LLM via Ollama (no external API; runs on your machine).
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")
    llm_timeout_s: int = _int("LLM_TIMEOUT_SECONDS", 60)

    # Local vLLM server (OpenAI-compatible /v1). vLLM's default port is 8000.
    # api_key is optional — a local vLLM ignores it unless started with one.
    vllm_base_url: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    vllm_api_key: str = os.getenv("VLLM_API_KEY", "")
    vllm_model: str = os.getenv("VLLM_MODEL", "local-model")

    seed_truck_count: int = _int("SEED_TRUCK_COUNT", 120)

    @property
    def llm_enabled(self) -> bool:
        # Only local providers exist; both are best-effort with geo fallback.
        return self.llm_provider in ("ollama", "vllm")

    @property
    def llm_label(self) -> str:
        """Human-readable backend label for logs/banners."""
        if not self.llm_enabled:
            return "off (geo-only)"
        if self.llm_provider == "ollama":
            return f"ollama:{self.ollama_model} @ {self.ollama_host}"
        return f"vllm:{self.vllm_model} @ {self.vllm_base_url}"


settings = Settings()
