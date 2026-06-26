# LogistAI — detailed guide

Reference docs that don't belong in the README's quick start. For the rationale
behind these choices see [`../DECISIONS.md`](../DECISIONS.md).

## How the matching works

`joriy_lokatsiya` (and `yuk_ortish_joyi`) may be a region/city name — in Latin
**or** Cyrillic, with suffixes like *shahri / viloyati* — **or** a raw GPS pair
`"41.31,69.24"`. `app/geo.py` normalizes and resolves any of these against a
built-in **Uzbekistan gazetteer**, then `haversine_km` measures distance.
The agent sorts trucks closest-first, keeps those within `MATCH_MAX_DISTANCE_KM`,
and records the top `MATCH_TOP_N`.

Each request is matched **synchronously the moment it's generated**. A background
**watcher** (`WATCH_INTERVAL_SECONDS`, default 10s) also scans for any request
created out-of-band (by another service, or while the agent was down) and matches
it — claiming rows with `FOR UPDATE SKIP LOCKED` so multiple workers can share
one backlog without double-matching (real locks on Postgres, no-op on SQLite).

## LLM re-rank layer

The geo-ranker is the deterministic core. On top of it an LLM re-ranks the
shortlist and adds a one-line rationale, via `LLM_PROVIDER`.

> **Constraint: no external ML / chatbot API.** Every provider runs **locally** —
> no Claude, no OpenAI, no cloud inference. There is no code path that calls a
> third-party model service.

| `LLM_PROVIDER` | Backend | Network | Setup |
|----------------|---------|---------|-------|
| `ollama` *(default)* | **local LLM** (Ollama) | **offline** | install Ollama + pull a model (else auto-falls back to geo) |
| `vllm` | **local vLLM** server (OpenAI-compatible `/v1`; also fits llama.cpp / LM Studio / LocalAI) | **offline** | run vLLM, set `VLLM_BASE_URL`/`VLLM_MODEL` |
| `none` | geo-ranking only | **offline** | nothing |

Whatever the provider, the call is best-effort: if the LLM is unavailable or
returns bad output, the agent silently keeps the geo order — it never depends on
the LLM to function. (`ollama` and `vllm` both talk plain HTTP via the stdlib,
so **no extra Python dependency** is added.) The startup banner shows the active
backend and `[reachable]` / `[unreachable -> geo fallback]`, and each match line
logs `via LLM` or `via geo (LLM fallback)`.

### Run with Ollama (default)

**Docker, one command** (auto-installs the server *and* the model):

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

Starts a local Ollama server, pulls the model automatically (defaults to the tiny
`qwen2.5:0.5b`), and runs the agent against it. First run downloads the model;
later runs are instant (cached in a volume). Pick another model with
`OLLAMA_MODEL=llama3.2:3b docker compose -f … up`.

**On your host:**

```bash
# 1. install Ollama from https://ollama.com  (one-click installer)
ollama pull qwen2.5:0.5b
LLM_PROVIDER=ollama OLLAMA_MODEL=qwen2.5:0.5b python -m app.runner
```

> **Tiny models:** `qwen2.5:0.5b` is great for a fast demo but too small to
> reason reliably about distances — it may re-order trucks worse than plain geo.
> The agent always falls back to the correct geo order, and the LLM's real value
> here is the human-readable *rationale*. For trustworthy re-ranking use a larger
> model (`llama3.2:3b`+).

### Run with vLLM (production-grade, GPU)

```bash
# start a local vLLM OpenAI-compatible server, e.g.
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-0.5B-Instruct
LLM_PROVIDER=vllm VLLM_MODEL=Qwen/Qwen2.5-0.5B-Instruct python -m app.runner
```

**Why Ollama default, vLLM optional?** Ollama is easiest (one-click, all OSes,
CPU) — ideal for a zero-friction demo. vLLM is the production choice:
GPU-accelerated, high-throughput batched serving. Because vLLM exposes the
OpenAI-compatible `/v1` API, the same `vllm` provider also drives llama.cpp /
LM Studio / LocalAI via `VLLM_BASE_URL`. All local; none call an external API.

## Run on Postgres

SQLite is the zero-config default. To use a real Postgres via Docker (the overlay
adds the DB and wires it up — no env vars needed):

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

Or point at any database yourself with `DATABASE_URL` in `.env`.

## Makefile shortcuts

Run `make help` to list them.

| Command | What it does |
|---------|--------------|
| `make install` | install core deps |
| `make migrate` | apply DB migrations (`alembic upgrade head`) |
| `make run` | seed + live generate/match loop |
| `make once` | single generate/match tick + analytics |
| `make analytics` | print agent performance summary |
| `make test` | run the test suite |
| `make docker` | `docker compose up` — SQLite, zero config |
| `make docker-postgres` | run the stack on Postgres |
| `make docker-ollama` | run with a local LLM (Ollama, auto-pulls the model) |
| `make ollama-pull` | manually (re)pull a model into the Ollama container |
| `make docker-down` | stop + remove the docker stack |

## Configuration (`.env`)

Copy `.env.example` to `.env` to override any default (all are optional):

| Var | Default | Meaning |
|-----|---------|---------|
| `DATABASE_URL` | `sqlite:///logistai.db` | any SQLAlchemy URL (Postgres-ready) |
| `REQUEST_MIN/MAX_INTERVAL_SECONDS` | `60` / `600` | request generation gap (1–10 min) |
| `MATCH_TOP_N` | `3` | recommendations logged per request |
| `MATCH_MAX_DISTANCE_KM` | `600` | max pickup distance considered |
| `SEED_TRUCK_COUNT` | `120` | fleet size seeded if `malumotlar` is empty |
| `LLM_PROVIDER` | `ollama` | re-rank backend (local only): `ollama` / `vllm` / `none` |
| `WATCH_INTERVAL_SECONDS` | `10` | how often the watcher matches externally-created requests (0 disables) |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | `localhost:11434` / `qwen2.5:0.5b` | local Ollama server + model |
| `VLLM_BASE_URL` / `VLLM_MODEL` | `localhost:8000/v1` / `local-model` | local vLLM server + model |
| `LLM_TIMEOUT_SECONDS` | `120` | per-request LLM timeout |

## Tests

```bash
python -m pytest
```

Coverage includes nearest-truck ranking correctness, the ≥400/day volume floor,
latency logging, the LLM dispatch/fallback paths, the watcher picking up
externally-created requests, and DB-level guarantees — NOT NULL columns,
foreign-key enforcement, server-side timestamp defaults, PK autoincrement, and
that both FK columns are indexed for join performance.

## Project layout

```
app/
  config.py          settings from .env
  database.py        SQLAlchemy engine / session / Base
  models.py          ORM models for the 3 tables
  geo.py             UZ gazetteer + transliteration + GPS parse + haversine
  matching_agent.py  the agent: rank → (LLM re-rank) → log + latency
  llm.py             local LLM providers (ollama / vllm), best-effort
  seed.py            truck-fleet seeder
  generator.py       auto request generator (≥400/day)
  runner.py          orchestrator: banner → seed → backfill → live loop + watcher
  analytics.py       latency / matched-ratio / distance summary
alembic/versions/    0001 zaproslar · 0002 malumotlar · 0003 agent_takliflari
```
