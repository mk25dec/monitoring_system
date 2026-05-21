# monitoring_system

Local, free stage monitoring for Python data jobs: **your code → Redis Stream → ingest → SQLite → Streamlit**.

Producers only send a small stable envelope; extra fields go in `data` (JSON) without changing Redis, ingest, or the dashboard contract.

## Architecture

```
Python modules ──emit()──► Redis Stream (stage:events)
                              │
                         ingest worker (ACK after SQLite commit)
                              ▼
                         SQLite (events + current_state)
                              ▼
                         Streamlit (ui_dashboard view, colors)
```

## Prerequisites

- [Pixi](https://pixi.sh)
- **Redis** running locally:
  - `docker compose up -d` (uses `docker-compose.yml` in this repo), or
  - `sudo apt install redis-server && sudo systemctl start redis-server`

## Quick start

```bash
cd /home/irene/Documents/GitHub/monitoring_system

# Install env + package
pixi install

# Optional: copy config / env
cp .env.example .env          # optional overrides
# cp config.default.toml config.toml  # optional

# Terminal 1 — persist events
pixi run ingest

# Terminal 2 — dashboard
pixi run dashboard

# Terminal 3 — example producer
pixi run example
```

Open the Streamlit URL (usually http://localhost:8501). You should see `demo-run-001` with colored rows.

## Configuration

| Source | Purpose |
|--------|---------|
| `config.default.toml` | Committed defaults |
| `config.toml` | Local overrides (gitignored) |
| `.env` | Env overrides, e.g. `MONITORING_REDIS__HOST=127.0.0.1` |
| `MONITORING_CONFIG` | Point to a custom TOML file |

Key settings: `redis.stream`, `sqlite.path`, `ingest.batch_size`, `dashboard.poll_seconds`.

## Connect any Python module

### Option A — install this repo editable (recommended)

From your other project (same machine):

```bash
pip install -e /home/irene/Documents/GitHub/monitoring_system
# or add to your pixi/pyproject:
# monitoring-system = { path = "../monitoring_system", editable = true }
```

In your pipeline code:

```python
from monitoring_system import emit, track

RUN_ID = "batch-2025-05-21"

emit(run_id=RUN_ID, module="myproject.etl.load", stage="extract", status="running")
# ... work ...
emit(run_id=RUN_ID, module="myproject.etl.load", stage="extract", status="done", data={"rows": 5000})

# Or context manager (running → done/failed):
with track(RUN_ID, "myproject.etl.transform", "normalize", data={"source": "s3"}):
    ...
```

Add arbitrary fields in `data` — they are stored in SQLite `payload` and shown in the dashboard expander:

```python
emit(..., status="running", data={"shard": 3, "memory_mb": 512, "custom_metric": 0.99})
```

### Option B — minimal copy-paste

If you cannot install the package, publish one line to Redis with the same JSON envelope (`schema_version`, `event_id`, `ts`, `run_id`, `module`, `stage`, `status`, `data`). See `src/monitoring_system/envelope.py`.

### Module naming

Use dotted names matching your code: `package.submodule.stage_name` so the table stays readable across many jobs.

### Offline / Redis down

`emit()` writes JSON files under `data/spool/`. Call `get_client().flush_spool()` when Redis is back.

## Running services (Pixi tasks)

| Task | Command |
|------|---------|
| Ingest worker | `pixi run ingest` |
| Dashboard | `pixi run dashboard` |
| Init SQLite schema | `pixi run init-db` |
| Example producer | `pixi run example` |
| Tests | `pixi run -e dev test` |

## Project layout

```
monitoring_system/
├── config.default.toml
├── .env.example
├── pixi.toml
├── pyproject.toml
├── src/monitoring_system/
│   ├── client.py          # Producer SDK
│   ├── envelope.py        # Event contract
│   ├── config.py
│   ├── db/                # SQLite schema + writes
│   ├── ingest/worker.py   # Redis → SQLite
│   └── dashboard/app.py   # Streamlit UI
└── examples/quick_emit.py
```

## Status colors (dashboard)

| Status | Color |
|--------|-------|
| `running` | Yellow |
| `done`, `completed`, `success` | Green |
| `failed`, `error` | Red |
| `pending` | Gray |
| Other | White |

## Git

```bash
git init
git add .
git commit -m "Initial monitoring_system scaffold"
```

## License

Use freely in your own projects.
