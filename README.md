# LogistAI — AI-agent freight ⇄ truck matching

An AI agent that watches automatically-generated freight requests and, the
moment a request appears, recommends the nearest available trucks to its
loading point — logging which truck it picked and how long it took to decide.

Implements the EGS GROUP test task (`TEST_TASK.md`).

> **100% offline — no external ML/chatbot API (no Claude, no OpenAI).** Matching
> is local geo-ranking; an optional LLM re-rank layer runs on a **local** model
> (Ollama by default, or vLLM), falling back to geo order if it isn't running.

---

## 🚀 Quick start

**Option A — Docker (no Python needed)**

```bash
docker compose up --build
```

Migrations run automatically, trucks are seeded, and the live generate-and-match
loop starts. Stop with `Ctrl+C`.

**Option B — Python**

```bash
pip install -r requirements.txt   # 1. install
python -m alembic upgrade head     # 2. create the database (3 migrations)
python -m app.runner               # 3. run the live loop (Ctrl+C to stop)
```

Prefer a quick one-shot result? `python -m app.runner --once`.

```bash
python -m app.analytics    # performance summary anytime
python -m pytest           # run the tests
make help                  # list all Makefile shortcuts
```

> **Tip:** requests use a 1–10 min interval (per the task). To watch activity
> immediately, set `REQUEST_MIN_INTERVAL_SECONDS=3` / `REQUEST_MAX_INTERVAL_SECONDS=5`
> in `.env`.

---

## What it does

1. **Generates freight requests** (`zaproslar`) automatically on a random
   **1–10 minute** interval, clearing the **≥ 400 requests/day** floor.
2. **Matches each request** the instant it's created: resolves the loading place
   (`yuk_ortish_joyi`), ranks every truck in `malumotlar` by great-circle
   distance, writes the top-N picks to `agent_takliflari`.
3. **Monitors latency** — each recommendation stores the request-created time,
   the recommendation time, and the measured decision latency.

```
 generator (APScheduler)          matching agent                 analytics
  every 1–10 min          ──►   resolve pickup → coords    ──►   avg/max latency
  create N zaproslar             rank trucks by haversine         matched ratio
                                 (optional local-LLM re-rank)     avg distance
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

## More

- **[docs/GUIDE.md](docs/GUIDE.md)** — matching internals, LLM providers
  (Ollama / vLLM), Postgres, full config reference, Makefile shortcuts, project
  layout, test coverage.
- **[DECISIONS.md](DECISIONS.md)** — design rationale and trade-offs.
