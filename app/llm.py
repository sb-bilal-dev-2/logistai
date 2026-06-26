"""Optional LLM re-rank layer.

The deterministic geo-ranker already produces a correct ordering by distance.
When a re-rank provider is enabled the agent additionally asks an LLM to act as
a dispatcher: confirm / adjust the ordering of the shortlisted candidates and
give a one-line rationale.

Two providers are supported, selected by `LLM_PROVIDER`:
  * "ollama" — a **locally installed** LLM served by Ollama (no external API,
    no key, runs on localhost). This is the recommended offline LLM option.
  * "claude" — Anthropic Claude (cloud API, needs a key).

Either way the call is best-effort: any failure (server down, model missing,
bad JSON, timeout) returns None and the caller keeps the geo order. The system
never depends on the LLM to function.
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
    """Re-rank shortlisted trucks via the configured LLM provider.

    `candidates` is a list of {mashina_id, mashina_raqami, lokatsiya, masofa_km}.
    Returns {"order": [mashina_id, ...], "rationale": str} or None on any
    failure (caller falls back to the deterministic geo order).
    """
    if not settings.llm_enabled:
        return None
    if settings.llm_provider == "ollama":
        return _rerank_ollama(loading_place, candidates)
    if settings.llm_provider == "claude":
        return _rerank_claude(loading_place, candidates)
    return None


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


def _rerank_claude(loading_place: str, candidates: list[dict]) -> Optional[dict]:
    """Call Anthropic Claude (cloud). Lazily imported so the dep stays optional."""
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.llm_model,
            max_tokens=400,
            messages=[{"role": "user", "content": _build_prompt(loading_place, candidates)}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        )
        return _parse(text)
    except Exception:
        return None
