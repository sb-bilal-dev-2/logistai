# LogistAI — AI-agent freight ⇄ truck matching

An AI agent that watches automatically-generated freight requests and, the
moment a request appears, recommends the nearest available trucks to its
loading point — logging which truck it picked and how long it took to decide.

This implements the EGS GROUP test task (`TEST_TASK.md`).

> **Runs 100% offline — no external API, no Claude, no OpenAI.** Matching uses
> local geo-ranking; an LLM re-rank layer is **on by default** using a **local**
> Ollama model (still offline). If Ollama isn't running it transparently falls
> back to geo order, so a fresh run never breaks. See *LLM re-rank layer* below.

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
python -m pytest           # run the tests
```

### Shortcuts (Makefile)

Every common command is wrapped in a `Makefile` — run `make help` to list them:

| Command | What it does |
|---------|--------------|
| `make install` | install core deps (offline, no AI SDK) |
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
                                   (optional local-LLM re-rank)    avg distance
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

### LLM re-rank layer

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
so **no extra Python dependency** is added.)

**Local LLM — no API key, nothing leaves your machine.** Two ways:

**Easiest — Docker, one command (auto-installs the server *and* the model):**

```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

That starts a local Ollama server, pulls the model automatically (defaults to the
tiny `qwen2.5:0.5b`), and runs the agent against it. First run downloads the
model; later runs are instant (it's cached in a volume). Pick another model with
`OLLAMA_MODEL=llama3.2:3b docker compose -f … up`.

**Without Docker (run Ollama on your host):**

```bash
# 1. install Ollama from https://ollama.com  (one-click installer)
# 2. pull a small model
ollama pull qwen2.5:0.5b
# 3. point the agent at it (in .env:  LLM_PROVIDER=ollama)
LLM_PROVIDER=ollama OLLAMA_MODEL=qwen2.5:0.5b python -m app.runner
```

> **Note on tiny models:** `qwen2.5:0.5b` is great for a fast demo, but it's too
> small to reason reliably about distances — it may re-order trucks worse than
> plain geo-ranking. That's fine: the agent always falls back to the correct geo
> order if the LLM is unavailable, and the LLM's value here is the human-readable
> *rationale*. For trustworthy re-ranking use a larger model (`llama3.2:3b`+).

**Using vLLM instead** (high-throughput local serving, GPU):

```bash
# start a local vLLM OpenAI-compatible server, e.g.
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-0.5B-Instruct
# point the agent at it
LLM_PROVIDER=vllm VLLM_MODEL=Qwen/Qwen2.5-0.5B-Instruct python -m app.runner
```

**Why Ollama as the default, and why vLLM as an option?** Ollama is the easiest
to install (one click, all OSes), manages model downloads, and runs on CPU —
ideal for a zero-friction local demo. vLLM is the production-grade choice:
GPU-accelerated, high-throughput batched serving. Because vLLM exposes the
OpenAI-compatible `/v1` API, the **same `vllm` provider** also works with other
local servers (llama.cpp, LM Studio, LocalAI) — just point `VLLM_BASE_URL` at
them. All local; none call an external API.

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
| `LLM_PROVIDER` | `ollama` | re-rank backend (local only): `ollama` (default) / `vllm` / `none` |
| `WATCH_INTERVAL_SECONDS` | `10` | how often the watcher matches externally-created requests (0 disables) |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | `localhost:11434` / `qwen2.5:0.5b` | local Ollama server + model |
| `VLLM_BASE_URL` / `VLLM_MODEL` | `localhost:8000/v1` / `local-model` | local vLLM (OpenAI-compatible) server + model |
| `LLM_TIMEOUT_SECONDS` | `120` | per-request LLM timeout |

All common commands are also wrapped in a `Makefile` — see *Shortcuts (Makefile)*
under Quick start, or run `make help`.

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
