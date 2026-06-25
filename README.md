# LogistAI — AI-agent freight ⇄ truck matching

An AI agent that watches automatically-generated freight requests and, the
moment a request appears, recommends the nearest available trucks to its
loading point — logging which truck it picked and how long it took to decide.

This implements the EGS GROUP test task (`TEST_TASK.md`).

---

## What it does

1. **Generates freight requests** (`zaproslar`) automatically on a random
   **1–10 minute** interval, at a rate that clears the **≥ 400 requests/day**
   floor.
2. **Matches each request** the instant it's created: the agent resolves the
   loading place (`yuk_ortish_joyi`), ranks every truck in `malumotlar` by
   great-circle distance, and writes the top-N picks to `agent_takliflari`.
3. **Monitors latency** — every recommendation row stores the request-created
   time, the recommendation time, and the measured decision latency.

```
 generator (APScheduler)          matching agent                 analytics
 ───────────────────────          ──────────────                 ─────────
  every 1–10 min                   resolve pickup → coords         avg/max latency
  create N zaproslar  ───────────► rank trucks by haversine  ───►  matched ratio
                                   (optional Claude re-rank)       avg distance
                                   write agent_takliflari + latency
```

## Data model (3 migrations, names per spec)

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `zaproslar` | freight requests | `yuk_ortish_joyi`, `yuk_tushirish_joyi`, `yuklash_sanasi` |
| `malumotlar` | trucks | `mashina_raqami`, `joriy_lokatsiya` |
| `agent_takliflari` | agent suggestion log | `zapros_id` (FK), `mashina_id` (FK), `zapros_yaratilgan_vaqti`, `agent_taklif_bergan_vaqti`, `reyting`, `masofa_km`, `latency_ms` |

Each table is created by its own Alembic migration under `alembic/versions/`
(`0001` → `0002` → `0003`), exactly as the task specifies.

## How the matching works

`joriy_lokatsiya` (and `yuk_ortish_joyi`) may be a region/city name — in Latin
**or** Cyrillic, with suffixes like *shahri / viloyati* — **or** a raw GPS pair
`"41.31,69.24"`. `app/geo.py` normalizes and resolves any of these against a
built-in **Uzbekistan gazetteer**, then `haversine_km` measures distance.
The agent sorts trucks closest-first, keeps those within
`MATCH_MAX_DISTANCE_KM`, and records the top `MATCH_TOP_N`.

**Optional LLM layer:** install the extra (`pip install -r requirements-llm.txt`),
then set `USE_LLM_RERANK=1` and `ANTHROPIC_API_KEY=…` to let Claude
(`claude-opus-4-8`) re-rank the shortlist and add a one-line rationale. Without
it the deterministic geo-ranker runs alone — the system is fully functional
offline and the base install pulls no AI SDK.

---

## Quick start

> **Runs fully offline — no Claude API required.** The base install pulls no
> AI SDK; the matching agent uses the deterministic geo-ranker. The Claude
> re-rank layer is strictly optional (see below).

```bash
# 1. install core deps (no API dependency)
python -m pip install -r requirements.txt

# 2. configure (optional — sensible SQLite defaults work out of the box)
cp .env.example .env

# 3. create the schema (runs all 3 migrations)
python -m alembic upgrade head

# 4a. one tick: seed trucks, create requests, match them, print analytics
python -m app.runner --once

# 4b. or run the live system (Ctrl+C to stop)
python -m app.runner
```

Useful individual commands:

```bash
python -m app.seed         # seed the truck fleet into malumotlar
python -m app.analytics    # print agent performance summary
```

### Run with Docker (no Python setup)

The fastest way to run locally — Docker applies migrations automatically and
starts the live loop on a persistent SQLite volume. No Python, no API key:

```bash
docker compose up --build
```

Use a real Postgres instead of SQLite (overlay file adds the DB and wires it up):

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

A `Makefile` wraps the common commands too: `make once`, `make test`,
`make docker`, `make docker-postgres`, `make docker-down`.

Example analytics output:

```
=== LogistAI agent analytics ===
  zaproslar               : 524
  malumotlar              : 120
  takliflar_log           : 1572
  matched_requests        : 524
  unmatched_requests      : 0
  avg_latency_ms          : 1.49
  avg_top1_distance_km    : 38.2
```

## Tests

```bash
python -m pytest        # 39 tests: geo, matching, generator, DB constraints
```

Coverage includes nearest-truck ranking correctness, the ≥400/day volume floor,
latency logging, and DB-level guarantees — NOT NULL columns, foreign-key
enforcement, server-side timestamp defaults, PK autoincrement, and that both FK
columns are indexed for join performance. See `DECISIONS.md` for the rationale
behind the design.

## Configuration (`.env`)

| Var | Default | Meaning |
|-----|---------|---------|
| `DATABASE_URL` | `sqlite:///logistai.db` | any SQLAlchemy URL (Postgres-ready) |
| `REQUEST_MIN/MAX_INTERVAL_SECONDS` | `60` / `600` | request generation gap (1–10 min) |
| `MATCH_TOP_N` | `3` | recommendations logged per request |
| `MATCH_MAX_DISTANCE_KM` | `600` | max pickup distance considered |
| `SEED_TRUCK_COUNT` | `120` | fleet size seeded if `malumotlar` is empty |
| `USE_LLM_RERANK` / `ANTHROPIC_API_KEY` | `0` / — | enable the Claude re-rank layer |

## Project layout

```
app/
  config.py          settings from .env
  database.py        SQLAlchemy engine / session / Base
  models.py          ORM models for the 3 tables
  geo.py             UZ gazetteer + transliteration + GPS parse + haversine
  matching_agent.py  the agent: rank → (LLM re-rank) → log + latency
  seed.py            truck-fleet seeder
  generator.py       auto request generator (≥400/day)
  runner.py          orchestrator: seed → backfill → live scheduler
  analytics.py       latency / matched-ratio / distance summary
alembic/versions/    0001 zaproslar · 0002 malumotlar · 0003 agent_takliflari
```

## Design notes

- **Robust to restarts:** on startup the runner backfills any requests that were
  created while the agent was down (`process_pending`), so nothing goes unmatched.
- **Reproducible demo:** the seed fleet uses a fixed RNG seed.
- **Latency is real:** measured with `perf_counter` around the actual ranking
  call and stored per recommendation, enabling the future efficiency/accuracy
  analytics the task asks for.
