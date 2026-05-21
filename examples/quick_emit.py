#!/usr/bin/env python3
"""Example: emit stages from any script (run ingest + dashboard first)."""

import time

from monitoring_system import emit, track

RUN = "demo-run-001"

emit(run_id=RUN, job="examples.quick_emit", stage="init", status="done")

with track(RUN, "examples.quick_emit", "process", data={"rows": 1000}):
    for pct in (10, 40, 70, 100):
        emit(
            run_id=RUN,
            job="examples.quick_emit",
            stage="process",
            status="running",
            data={"progress": pct, "rows": 1000},
        )
        time.sleep(0.3)

emit(
    run_id=RUN,
    job="examples.quick_emit",
    stage="export",
    status="running",
    data={"format": "parquet", "progress_pct": 25},
)
emit(
    run_id=RUN,
    job="examples.quick_emit",
    stage="export",
    status="done",
    data={"format": "parquet", "progress_pct": 100},
)

# Example failed stage (shows red LED in UI)
emit(
    run_id=RUN,
    job="examples.quick_emit",
    stage="validate",
    status="failed",
    data={"progress": 60, "error": "schema mismatch"},
)

print(f"Emitted stages for run_id={RUN}")
