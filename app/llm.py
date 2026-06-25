"""Optional LLM reasoning layer (Anthropic Claude).

The deterministic geo-ranker already produces a correct ordering by distance.
When `USE_LLM_RERANK=1` and an API key is present, we additionally ask Claude
to act as a dispatcher: confirm / adjust the ordering of the shortlisted
candidates and give a one-line rationale. This demonstrates the "AI agent"
layer while keeping the system fully functional without any API key.
"""
from __future__ import annotations

import json
from typing import Optional

from app.config import settings


def llm_rerank(loading_place: str, candidates: list[dict]) -> Optional[dict]:
    """Ask Claude to re-rank shortlisted trucks.

    `candidates` is a list of {mashina_id, mashina_raqami, lokatsiya, masofa_km}.
    Returns {"order": [mashina_id, ...], "rationale": str} or None on any failure
    (caller falls back to the deterministic order).
    """
    if not settings.llm_enabled:
        return None

    try:
        import anthropic  # imported lazily so the dep is optional
    except ImportError:
        return None

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    prompt = (
        "You are a freight dispatch agent. A new shipment must be picked up at "
        f"'{loading_place}'. Below are candidate trucks with their current "
        "location and great-circle distance (km) to the pickup point. Re-rank "
        "them from best to worst pickup choice (closest is usually best, but you "
        "may weigh ties sensibly) and give a short rationale.\n\n"
        f"Candidates JSON:\n{json.dumps(candidates, ensure_ascii=False)}\n\n"
        "Respond with ONLY valid JSON: "
        '{"order": [mashina_id, ...], "rationale": "..."}'
    )

    try:
        msg = client.messages.create(
            model=settings.llm_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text for block in msg.content if getattr(block, "type", "") == "text"
        ).strip()
        # Be tolerant of code fences.
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1]
        data = json.loads(text)
        if isinstance(data, dict) and isinstance(data.get("order"), list):
            return data
    except Exception:
        return None
    return None
