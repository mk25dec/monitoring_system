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

Run **`./start`** before your program. Your script sends updates with `emit()`; the dashboard shows what you send (it does not compute progress or job totals).

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

### `emit()` parameters

All arguments are **keyword-only** (`emit(run_id="…", …)`).

| Parameter | Required | Description |
|-----------|----------|-------------|
| `run_id` | yes | One ID for the whole run (e.g. `export-abc123`, `batch-2026-05-21`). Every step in that execution shares this value. |
| `job` | yes | Program or pipeline name (e.g. `samples.export`, `billing.etl`). Shown in the **Job** column. |
| `stage` | yes | Step name (e.g. `package`, `upload`, `validate`). Shown in the **Stage** column. |
| `status` | yes | Step state. Use a **running** value while working, then a **terminal** value when finished. See [status values](#status-values) below. |
| `sequence` | no | Step order within this `run_id` + `job` (use **1, 2, 3…**). Same `stage` name twice → use a new sequence each time. If omitted, numbers auto-increment (1, 2, 3…) per run + job. **Do not use 0** (reserved for the dashboard job summary row). |
| `message` | no | Short text for the **Message** column (e.g. `Reading files`, `Upload complete`). |
| `error` | no | Error text for the **Error** column. Use with `status="failed"` (or similar). |
| `data` | no | Extra fields stored as JSON. Use for **progress** and any custom keys. See [data dict](#data-dict) below. |
| `module` | no | Deprecated alias for `job`. Prefer `job`. |

Returns: `event_id` (string) for the emitted event.

### Status values

| Kind | Example `status` values | Dashboard light |
|------|-------------------------|-------------------|
| In progress | `running`, `in_progress`, `processing`, `started`, `pending` | Amber |
| Success | `done`, `completed`, `success`, `ok`, `passed` | Green |
| Failed | `failed`, `error`, `failure`, `crashed`, `cancelled` | Red |
| Other | anything else | Gray |

Typical pattern per step: one `emit` with a **running** status, then one with **done** or **failed**.

### `data` dict

Put display numbers and labels in `data` so the UI can show them without calculating:

| Key in `data` | Purpose |
|---------------|---------|
| `progress` | 0–100 (or 0.0–1.0, treated as fraction). Shown as the progress bar. |
| `progress_pct`, `percent`, `pct` | Same as progress (0–100). |
| `message`, `error` | Optional; copied to columns if not passed as top-level `message` / `error`. |

Example with failure:

```python
emit(
    run_id="batch-42",
    job="myprogram",
    stage="validate",
    status="failed",
    sequence=3,
    message="Validation failed",
    error="checksum mismatch",
    data={"progress": 60},
)
```

### Optional: `track()` context manager

Emits **running** on entry and **done** / **failed** on exit (re-raises exceptions):

```python
from monitoring_system import track

with track(run_id="batch-42", job="myprogram", stage="import", sequence=1, message="Import"):
    ...  # your code ...
```

`track()` accepts the same `run_id`, `job`, `stage`, `sequence`, `message`, and `data` as `emit()`, plus optional `ok_status` (default `done`) and `fail_status` (default `failed`).
