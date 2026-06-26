"""Optional LLM re-rank layer — LOCAL MODELS ONLY.

The deterministic geo-ranker already produces a correct ordering by distance.
When a re-rank provider is enabled the agent additionally asks an LLM to act as
a dispatcher: confirm / adjust the ordering of the shortlisted candidates and
give a one-line rationale.

CONSTRAINT: no external ML / chatbot API is used. Both supported providers run
on the local machine and never call a third-party service:
  * "ollama" — a locally installed LLM served by Ollama (default).
  * "vllm"   — a local vLLM server (OpenAI-compatible /v1 API). The same code
    also works with other local /v1 servers (llama.cpp, LM Studio, LocalAI) by
    pointing VLLM_BASE_URL at them.

Every call is best-effort: any failure (server down, model missing, bad JSON,
timeout) returns None and the caller keeps the geo order. The system never
depends on the LLM to function.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from app.config import settings


def _build_prompt(loading_place: str, candidates: list[dict]) -> str:
    return (
        "You are a freight dispatch agent. A new shipment must be picked up at "
        f"'{loading_place}'. Below are candidate trucks with their current "
        "location and great-circle distance (km) to the pickup point. Re-rank "
        "them from best to worst pickup choice (closest is usually best, but you "
        "may weigh ties sensibly) and give a short rationale.\n\n"
        f"Candidates JSON:\n{json.dumps(candidates, ensure_ascii=False)}\n\n"
        "Respond with ONLY valid JSON of the form: "
        '{"order": [mashina_id, ...], "rationale": "..."}'
    )


def _parse(text: str) -> Optional[dict]:
    """Parse a model's reply into the {order, rationale} contract."""
    text = (text or "").strip()
    if text.startswith("```"):  # tolerate ```json fences
        text = text.strip("`")
        text = text.split("\n", 1)[-1] if "\n" in text else text
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(data, dict) and isinstance(data.get("order"), list):
        return data
    return None


def llm_rerank(loading_place: str, candidates: list[dict]) -> Optional[dict]:
    """Re-rank shortlisted trucks via the configured local LLM provider.

    `candidates` is a list of {mashina_id, mashina_raqami, lokatsiya, masofa_km}.
    Returns {"order": [mashina_id, ...], "rationale": str} or None on any
    failure (caller falls back to the deterministic geo order).
    """
    if not settings.llm_enabled:
        return None
    if settings.llm_provider == "ollama":
        return _rerank_ollama(loading_place, candidates)
    if settings.llm_provider == "vllm":
        return _rerank_vllm(loading_place, candidates)
    return None


def llm_reachable() -> bool:
    """Quick check whether the active local LLM server is up (for banners)."""
    p = settings.llm_provider
    try:
        if p == "ollama":
            req = urllib.request.Request(settings.ollama_host.rstrip("/") + "/api/tags")
        elif p == "vllm":
            req = urllib.request.Request(settings.vllm_base_url.rstrip("/") + "/models")
            if settings.vllm_api_key:
                req.add_header("Authorization", f"Bearer {settings.vllm_api_key}")
        else:
            return False
        with urllib.request.urlopen(req, timeout=2) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _rerank_ollama(loading_place: str, candidates: list[dict]) -> Optional[dict]:
    """Call a locally-running Ollama server (stdlib HTTP, no extra deps)."""
    url = settings.ollama_host.rstrip("/") + "/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": _build_prompt(loading_place, candidates)}],
        "stream": False,
        "format": "json",  # ask Ollama to constrain output to JSON
        "options": {"temperature": 0},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.llm_timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = (body.get("message") or {}).get("content", "")
        return _parse(content)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        # Server not running / model not pulled / slow / malformed -> geo fallback.
        return None


def _rerank_vllm(loading_place: str, candidates: list[dict]) -> Optional[dict]:
    """Call a local vLLM server via its OpenAI-compatible /v1/chat/completions."""
    url = settings.vllm_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.vllm_model,
        "messages": [{"role": "user", "content": _build_prompt(loading_place, candidates)}],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json"}
    if settings.vllm_api_key:
        headers["Authorization"] = f"Bearer {settings.vllm_api_key}"
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=settings.llm_timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return _parse(content)
    except (
        urllib.error.URLError,
        TimeoutError,
        KeyError,
        IndexError,
        json.JSONDecodeError,
        ValueError,
        OSError,
    ):
        return None
