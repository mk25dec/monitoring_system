# Stage Monitor

A simple web dashboard for Python jobs: see each step as **in progress**, **done**, or **failed** (amber / green / red).

No need to run Docker or multiple terminals yourself — use **`./start`** and **`./stop`**.

---

## Before the first time

| Install | Link |
|---------|------|
| **Pixi** (runs the monitor software) | https://pixi.sh |
| **Docker Desktop** (local database; keep it **running**) | https://www.docker.com/products/docker-desktop/ |

Open a terminal **in this project folder** (where you see `start` and `stop`).

---

## Start the whole engine

```bash
./start
```

The script does everything for you:

1. Installs software on first run (`pixi install`)
2. Starts the database (`docker compose up -d`)
3. Prepares the local database
4. Starts the background saver (ingest)
5. Starts the web dashboard

Then open: **http://localhost:8501**

Same command via Pixi: `pixi run start`

---

## Stop the whole engine

```bash
./stop
```

The script stops the dashboard, background saver, and Docker database (if `./start` started it).

Same command via Pixi: `pixi run stop`

Check if things are running: `pixi run monitor-status`

---

## Try a demo job

With `./start` still running, in **another** terminal:

```bash
pixi run sample-etl
pixi run sample-export
```

Watch new rows appear on the dashboard.

---

## Something wrong?

| Problem | Fix |
|---------|-----|
| `Docker is not running` | Open Docker Desktop, wait until it says running, then `./start` again |
| `Pixi is not installed` | Install Pixi, **close and reopen** the terminal, then `./start` |
| Dashboard is empty | Run `./start`, then `pixi run sample-etl` |
| Browser does not open | Open **http://localhost:8501** manually |

---

## Adding monitoring to your own Python job

Your script sends updates; the dashboard only displays them (no calculations in the UI).

```python
from monitoring_system import emit

emit(
    run_id="batch-42",
    job="myprogram",
    stage="import",
    status="running",
    sequence=1,
    message="Reading files",
    data={"progress": 25},
)
# ... do work ...
emit(
    run_id="batch-42",
    job="myprogram",
    stage="import",
    status="done",
    sequence=1,
    message="Import finished",
    data={"progress": 100},
)
```

Keep **`./start`** running while your job runs. Use `sequence` 1, 2, 3… for step order. On failure use `status="failed"` and `error="…"`.
