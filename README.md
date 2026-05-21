# Stage Monitor

This tool shows what your Python programs are doing — which step is running, which finished, which failed — in a web page with green / amber / red lights.

You do **not** change your programs every time. You start the monitor once, then run your jobs as usual.

---

## What you need on your computer first

1. **Pixi** — installs the monitor software.  
   Install from: https://pixi.sh  

2. **Redis** — a small background service that receives updates.  
   Easiest way (if you have Docker): open a terminal in this folder and run:
   ```bash
   docker compose up -d
   ```
   Leave that running (or run it once before each session).

3. **This folder** — open a terminal here:
   ```bash
   cd /home/irene/Documents/GitHub/monitoring_system
   ```

4. **One-time setup** (only the first time):
   ```bash
   pixi install
   pixi run init-db
   ```

5. **Quick test** (Redis must be running):
   ```bash
   pixi run test-e2e
   ```
   You should see `All checks passed.`

---

## If something does not work

| Problem | Fix |
|---------|-----|
| `Connection refused` on Redis | Start Redis: `docker compose up -d` or `sudo systemctl start redis-server` |
| Empty dashboard | Terminal 1 must run `pixi run ingest`. Then run a sample job. |
| `no such column: job` | Run `pixi run init-db` once (fixes old databases). |
| KPI cards white / filter dead | Hard-refresh browser (`Ctrl+Shift+R`) after `pixi run dashboard` |

---

## Easy way — one command (recommended)

```bash
cd /home/irene/Documents/GitHub/monitoring_system
pixi run monitor-start    # starts Redis + ingest + dashboard
```

Open http://localhost:8501 in your browser.

```bash
pixi run monitor-stop     # stops dashboard + ingest (+ Docker Redis if this script started it)
pixi run monitor-status   # check what is running
```

Or use the script directly: `./scripts/monitor.sh start|stop|status|restart`

---

## Manual way (3 terminals)

You need **3 separate terminal windows**. Think of them as three programs that must stay open.

### Terminal 1 — “Save updates”

Copy and paste, press Enter:

```bash
cd /home/irene/Documents/GitHub/monitoring_system
pixi run ingest
```

Leave this window open. You should see it waiting (no error about Redis).

---

### Terminal 2 — “Show the web page”

Open a **new** terminal. Copy and paste:

```bash
cd /home/irene/Documents/GitHub/monitoring_system
pixi run dashboard
```

Leave this open. Your browser should open **http://localhost:8501**  
If it does not, copy that address into Chrome or Firefox.

This is your **dashboard** — the table with lights and progress bars.

---

### Terminal 3 — “Run a test job” (optional, to try it)

Open a **third** terminal. Pick **one** line to paste (or run all three, one after another):

```bash
cd /home/irene/Documents/GitHub/monitoring_system
pixi run sample-etl
```

Or:

```bash
pixi run sample-training
```

Or:

```bash
pixi run sample-export
```

Watch **Terminal 2’s browser page** — rows should appear and lights should change.

You can run more test jobs anytime while Terminals 1 and 2 stay open.

---

## Quick checklist

| Step | Terminal | Command | Keep open? |
|------|----------|---------|------------|
| A | Any | `docker compose up -d` | Redis can stay running in background |
| B | 1 | `pixi run ingest` | Yes |
| C | 2 | `pixi run dashboard` | Yes — use the browser page |
| D | 3+ | `pixi run sample-etl` (etc.) | No — runs and finishes |

**Order:** A once → B → C → then D whenever you want.

---

## When something goes wrong

| Problem | What to try |
|---------|-------------|
| Redis error | Run `docker compose up -d` in this folder |
| Empty dashboard | Make sure Terminal 1 (`ingest`) is running, then run a sample job again |
| Page won’t open | Go to http://localhost:8501 manually |
| “pixi not found” | Install Pixi from https://pixi.sh and open a **new** terminal |

---

## Using your own Python programs later

Your programmer (or you, with a little help) adds two lines to your script:

```python
from monitoring_system import emit

# sequence = step order in the job (1, 2, 3…). Same stage name twice → use a new sequence each time.
emit(
    run_id="job-1",
    job="myprogram",
    stage="step1",
    status="running",
    sequence=1,
    message="Reading input files",
)
# ... do work ...
emit(
    run_id="job-1",
    job="myprogram",
    stage="step1",
    status="done",
    sequence=1,
    message="Step 1 finished",
)

# On failure or crash:
emit(
    run_id="job-1",
    job="myprogram",
    stage="step2",
    status="failed",
    sequence=2,
    message="Export failed",
    error="disk full",
)
```

Omit `sequence` and the client assigns the next number automatically (1, 2, 3…) for that run + job.
The dashboard sorts by **Seq** so users see step order. **Message** and **Error** columns show both fields.

The monitor must still be running (Terminal 1 + 2) when your program runs.

---

## All commands in one place

Run these from: `/home/irene/Documents/GitHub/monitoring_system`

| What you want | Paste this |
|---------------|------------|
| First-time setup | `pixi install` |
| Start Redis (Docker) | `docker compose up -d` |
| Save updates (Terminal 1) | `pixi run ingest` |
| Open dashboard (Terminal 2) | `pixi run dashboard` |
| Test job — ETL | `pixi run sample-etl` |
| Test job — training | `pixi run sample-training` |
| Test job — export (has a failure) | `pixi run sample-export` |
