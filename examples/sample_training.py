#!/usr/bin/env python3
"""Sample 2: training job — preprocess → train → evaluate."""

import argparse
import time
import uuid

from monitoring_system import emit, track

JOB = "samples.training"
DEFAULT_SLEEP = 1.5


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample training job for stage monitor")
    parser.add_argument("--run-id", default=f"train-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Seconds per step")
    parser.add_argument("--epochs", type=int, default=5)
    args = parser.parse_args()
    run_id = args.run_id
    delay = args.sleep

    print(f"[sample_training] starting run_id={run_id}")

    with track(run_id, JOB, "preprocess", sequence=1, data={"version": "v1"}):
        time.sleep(delay * 2)

    emit(run_id=run_id, job=JOB, stage="train", status="running", sequence=2, data={"progress": 0})
    for epoch in range(1, args.epochs + 1):
        time.sleep(delay)
        pct = int(epoch / args.epochs * 100)
        emit(
            run_id=run_id,
            job=JOB,
            stage="train",
            status="running",
            sequence=2,
            data={"epoch": epoch, "epochs": args.epochs, "progress_pct": pct},
        )
        print(f"[sample_training] epoch {epoch}/{args.epochs}")
    emit(
        run_id=run_id,
        job=JOB,
        stage="train",
        status="done",
        sequence=2,
        data={"progress_pct": 100},
    )

    with track(run_id, JOB, "evaluate", sequence=3, data={"metric": "accuracy"}):
        time.sleep(delay * 2)

    print(f"[sample_training] done run_id={run_id}")


if __name__ == "__main__":
    main()
