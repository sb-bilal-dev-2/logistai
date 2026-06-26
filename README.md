# LogistAI — AI-agent freight ⇄ truck matching

An AI agent that watches automatically-generated freight requests and, the
moment a request appears, recommends the nearest available trucks to its
loading point — logging which truck it picked and how long it took to decide.

This implements the EGS GROUP test task (`TEST_TASK.md`).

> **Runs 100% offline by default — no API key, no Claude, no OpenAI.** Matching
> is pure local geo-ranking. An optional LLM re-rank layer can run on a **local**
> model (Ollama) — still no external API. See *Optional LLM re-rank layer* below.

---

## 🚀 Quick start

Pick **one** of the two options below.

### Option A — Docker (no Python needed)

```bash
docker compose up --build
```

That's it. Migrations run automatically, trucks are seeded, and the live
generate-and-match loop starts. Stop with `Ctrl+C`.

### Option B — Python

```bash
pip install -r requirements.txt     # 1. install
python -m alembic upgrade head       # 2. create the database
python -m app.runner                 # 3. run (Ctrl+C to stop)
```

Want a quick result instead of the live loop? Run one tick and see the numbers:

```bash
python -m app.runner --once
```

You should see something like:

```
[seed] inserted 120 trucks into malumotlar
[once] created+matched requests: [1, 2, 3]
=== LogistAI agent analytics ===
  zaproslar               : 3
  malumotlar              : 120
  takliflar_log           : 9
  matched_requests        : 3
  avg_latency_ms          : 1.31
```

### Handy commands

```bash
python -m app.analytics    # print agent performance summary anytime
python -m pytest           # run the 39 tests
```

> **Tip:** requests default to a 1–10 min interval (per the task). To watch
> activity right away, lower it in `.env`:
> `REQUEST_MIN_INTERVAL_SECONDS=3` and `REQUEST_MAX_INTERVAL_SECONDS=5`.

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

### Optional LLM re-rank layer

The geo-ranker is the deterministic core. On top of it you can optionally enable
an LLM to re-rank the shortlist and add a one-line rationale, via `LLM_PROVIDER`:

| `LLM_PROVIDER` | Backend | Network | Setup |
|----------------|---------|---------|-------|
| `none` *(default)* | geo-ranking only | **offline** | nothing |
| `ollama` | **local LLM** (Ollama) | **offline** | install Ollama + pull a model |
| `claude` | Anthropic Claude | cloud API | `pip install -r requirements-llm.txt` + key |

Whatever the provider, the call is best-effort: if the LLM is unavailable or
returns bad output, the agent silently keeps the geo order — it never depends on
the LLM to function.

**Local LLM (recommended offline option) — no API key, nothing leaves your machine:**

```bash
# 1. install Ollama from https://ollama.com, then pull a small model
ollama pull llama3.2

# 2. point the agent at it
#    in .env:  LLM_PROVIDER=ollama   (OLLAMA_MODEL defaults to llama3.2)
python -m app.runner
```

Or run the whole thing — app **and** a local Ollama server — in Docker:

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
# then pull the model once into the ollama container:
docker compose -f docker-compose.yml -f docker-compose.ollama.yml exec ollama ollama pull llama3.2
```

## Run on Postgres (optional)

SQLite is the zero-config default. To use a real Postgres via Docker (the
overlay adds the DB and wires it up — no env vars needed):

```bash
docker compose -f docker-compose.yml -f docker-compose.postgres.yml up --build
```

Or point at any database yourself with `DATABASE_URL` in `.env`.

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

Copy `.env.example` to `.env` to override any default (all are optional):

| Var | Default | Meaning |
|-----|---------|---------|
| `DATABASE_URL` | `sqlite:///logistai.db` | any SQLAlchemy URL (Postgres-ready) |
| `REQUEST_MIN/MAX_INTERVAL_SECONDS` | `60` / `600` | request generation gap (1–10 min) |
| `MATCH_TOP_N` | `3` | recommendations logged per request |
| `MATCH_MAX_DISTANCE_KM` | `600` | max pickup distance considered |
| `SEED_TRUCK_COUNT` | `120` | fleet size seeded if `malumotlar` is empty |
| `LLM_PROVIDER` | `none` | re-rank backend: `none` / `ollama` (local) / `claude` (cloud) |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | `localhost:11434` / `llama3.2` | local LLM server + model |
| `ANTHROPIC_API_KEY` / `LLM_MODEL` | — / `claude-opus-4-8` | only used when `LLM_PROVIDER=claude` |

A `Makefile` also wraps the common commands: `make once`, `make test`,
`make docker`, `make docker-postgres`, `make docker-down`.

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
