#!/usr/bin/env python3
"""Example: emit stages from any script (run ingest + dashboard first)."""

from monitoring_system import emit, track

RUN = "demo-run-001"

emit(run_id=RUN, module="examples.quick_emit", stage="init", status="done")

with track(RUN, "examples.quick_emit", "process", data={"rows": 1000}):
    # your work here
    pass

emit(
    run_id=RUN,
    module="examples.quick_emit",
    stage="export",
    status="running",
    data={"format": "parquet", "custom_metric": 42},
)
emit(run_id=RUN, module="examples.quick_emit", stage="export", status="done")

print(f"Emitted stages for run_id={RUN}")
