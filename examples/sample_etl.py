#!/usr/bin/env python3
"""Sample 1: ETL pipeline — extract → transform → load (all success)."""

import argparse
import time
import uuid

from monitoring_system import emit, track

JOB = "samples.etl"
DEFAULT_SLEEP = 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample ETL job for stage monitor")
    parser.add_argument("--run-id", default=f"etl-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Seconds per stage")
    args = parser.parse_args()
    run_id = args.run_id
    delay = args.sleep

    print(f"[sample_etl] starting run_id={run_id}")

    stages = [
        (1, "extract", "read raw files"),
        (2, "transform", "normalize rows"),
        (3, "load", "write to warehouse"),
    ]
    for seq, stage, label in stages:
        with track(
            run_id,
            JOB,
            stage,
            sequence=seq,
            data={"label": label, "progress": 0},
        ) as payload:
            for pct in (25, 50, 75, 100):
                time.sleep(delay / 4)
                payload["progress"] = pct
                emit(
                    run_id=run_id,
                    job=JOB,
                    stage=stage,
                    status="running",
                    sequence=seq,
                    message=f"{stage}: {pct}%",
                    data=dict(payload),
                )
            payload["progress"] = 100
        print(f"[sample_etl] finished step {seq} stage={stage}")

    print(f"[sample_etl] done run_id={run_id}")


if __name__ == "__main__":
    main()
