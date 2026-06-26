# Design decisions

Short rationale for the choices made in LogistAI.

## Stack
- **Python + SQLAlchemy 2.0 + Alembic.** The role is a Python AI/ML role and the
  task explicitly says "migration", so a real migration tool (Alembic) was used
  rather than `create_all`. Each of the three tables gets its own migration
  (`0001`→`0002`→`0003`), matching the spec's "first/second/third migration".
- **SQLite by default, Postgres-ready.** Zero setup for a reviewer (`upgrade head`
  and go), but `DATABASE_URL` accepts any SQLAlchemy URL. Migrations use
  `render_as_batch=True` so SQLite ALTERs stay compatible.
- **APScheduler** for the 1–10 min generation loop — lightweight, in-process, no
  broker needed for a demo. In production this would move to a durable queue /
  Celery beat, but the generation + matching code is unchanged by that swap.

## Matching approach (why geo + optional LLM, not a trained model)
- The core signal the task asks for is **proximity** ("eng yaqin yoki shu hududda
  turgan mashinalar"). That's a deterministic geospatial problem, so the base
  ranker is **haversine distance** over a built-in **Uzbekistan gazetteer**. It's
  correct, explainable, instant (~1.5 ms/request), and needs no API or GPU.
- Locations are messy: region/city names in **Latin or Cyrillic**, with admin
  suffixes (*shahri/viloyati*), or **raw GPS pairs**. `geo.py` normalizes
  (transliterate → strip noise → token match) and falls back to GPS parsing, so
  both input shapes resolve.
- The **"AI agent" / Generative-AI** dimension from the vacancy is satisfied by
  an **optional LLM re-rank layer** (`LLM_PROVIDER`): the LLM acts as a
  dispatcher that confirms/adjusts the shortlist and gives a rationale. It is
  strictly additive and degrades gracefully — if the LLM is unavailable or
  returns bad output, the deterministic geo order stands, so the system never
  depends on it to function.
- **The LLM is always local — no external ML/chatbot API is allowed.** Two
  providers, both on `localhost`, both called via stdlib HTTP (zero added pip
  deps): `ollama` (default; easiest, CPU-friendly) and `vllm` (production-grade,
  GPU, high-throughput). vLLM speaks the OpenAI-compatible `/v1` API, so the same
  provider also drives llama.cpp / LM Studio / LocalAI via `VLLM_BASE_URL`. There
  is no code path to a third-party model service — the "AI agent uses a generative
  model" story holds with nothing leaving the machine, demonstrating the JD's
  "deploy AI/ML models in production" without vendor lock-in.
- A learned ranking model (the PyTorch/TensorFlow part of the JD) is the natural
  next step once `agent_takliflari` accumulates labelled outcomes (accepted vs.
  rejected matches). The schema already logs distance + latency per pick to feed
  that future model — see "Future work".

## Watching for new requests (hybrid)
The agent matches each request **synchronously the moment it's generated** (lowest
latency, most faithful to *"zapros yaratilgan zahoti"*). On top of that a
**continuous watcher** (`process_pending`, every `WATCH_INTERVAL_SECONDS`) scans
for any request created **out-of-band** — by another service, or while the agent
was down — and matches it in near-real-time. Pending rows are claimed with
`FOR UPDATE SKIP LOCKED`, so multiple agent workers can share one backlog without
double-matching (real row locks on PostgreSQL; a harmless no-op on SQLite). This
gives the simplicity/latency of synchronous matching **and** the
decoupled/production behaviour of a queue consumer.

## LLM re-rank on by default (local)
`LLM_PROVIDER` defaults to `ollama` — the re-rank layer is **on**, using a local
model, so the "AI agent" genuinely reasons over candidates out of the box while
staying offline. It degrades gracefully: if the Ollama server isn't running the
agent falls back to the deterministic geo order (the startup banner shows
`[reachable]` / `[unreachable -> geo fallback]`). Set `LLM_PROVIDER=none` for
pure geo-ranking. Note the cost: a CPU LLM adds ~1–6 s/request of latency, which
is fine at the spec's 1–10 min cadence; for latency-critical use, `none` is best.

## Reliability choices
- **Backfill on startup** (`process_pending`): any request created while the
  agent was down is matched on next boot, so nothing is silently lost.
- **Never-starve shortlist:** if no truck resolves to coordinates, the agent
  still returns its best-effort candidates rather than producing zero matches.
- **Distances are nullable.** An unresolved location yields `masofa_km = NULL`
  (sorted last) instead of crashing or guessing a bogus 0.
- **Latency measured around the real ranking call** with `perf_counter`, stored
  per row — this is the monitoring signal the task asks for.
- **Daily-volume floor is guaranteed, not just average.** Worst case is the max
  600 s interval → 144 ticks/day; with `BATCH=3` that's 432 ≥ 400. Average
  interval gives ~785/day. (See `generator.py`.)

## Schema extras beyond the spec
`agent_takliflari` adds `reyting`, `masofa_km`, `latency_ms`, `izoh`. These are
cheap and turn the log into an analytics-ready table (matched ratio, avg
latency, avg pickup distance) — the "future analytics" the task anticipates.

## Future work
- Replace gazetteer centroids with a real geocoder + live truck GPS telemetry.
- Add truck **availability/capacity** (status, cargo type) to the ranking.
- Train a learning-to-rank model on accepted/rejected suggestions; serve it
  behind the same `matching_agent` interface.
- Move generation/matching onto a durable queue for horizontal scale.
