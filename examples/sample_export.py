#!/usr/bin/env python3
"""Sample 3: export job — package → upload → validate (may fail)."""

import argparse
import time
import uuid

from monitoring_system import emit

JOB = "samples.export"
DEFAULT_SLEEP = 2


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample export job for stage monitor")
    parser.add_argument("--run-id", default=f"export-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP, help="Seconds per stage")
    parser.add_argument("--fail", action="store_true", help="Force validate stage to fail")
    args = parser.parse_args()
    run_id = args.run_id
    delay = args.sleep

    print(f"[sample_export] starting run_id={run_id}")

    steps = [
        (1, "package", "bundle artifacts"),
        (2, "upload", "push to storage"),
        (3, "validate", "check output"),
    ]
    for seq, stage, label in steps:
        emit(
            run_id=run_id,
            job=JOB,
            stage=stage,
            status="running",
            sequence=seq,
            message=f"Running {stage}",
            data={"progress": 10, "label": label},
        )
        time.sleep(delay)
        if stage == "validate" and args.fail:
            emit(
                run_id=run_id,
                job=JOB,
                stage=stage,
                status="failed",
                sequence=seq,
                message="Validation failed",
                error="checksum mismatch",
                data={"progress": 60, "label": label},
            )
            print(f"[sample_export] validate FAILED run_id={run_id}")
            return
        emit(
            run_id=run_id,
            job=JOB,
            stage=stage,
            status="done",
            sequence=seq,
            message=f"{stage} completed",
            data={"progress": 100, "label": label},
        )
        print(f"[sample_export] finished step {seq} stage={stage}")

    print(f"[sample_export] done run_id={run_id}")


if __name__ == "__main__":
    main()
