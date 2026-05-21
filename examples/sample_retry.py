#!/usr/bin/env python3
"""Sample: same stage name twice — each call gets its own Seq (4 and 5)."""

import argparse
import time
import uuid

from monitoring_system import emit

JOB = "samples.retry"
DEFAULT_SLEEP = 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Same stage twice with different sequence numbers")
    parser.add_argument("--run-id", default=f"retry-{uuid.uuid4().hex[:8]}")
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP)
    args = parser.parse_args()
    run_id = args.run_id

    print(f"[sample_retry] run_id={run_id}")

    emit(
        run_id=run_id,
        job=JOB,
        stage="warmup",
        status="done",
        sequence=1,
        message="Warmup ok",
    )
    time.sleep(args.sleep)

    for attempt, seq in enumerate((4, 5), start=1):
        emit(
            run_id=run_id,
            job=JOB,
            stage="validate",
            status="running",
            sequence=seq,
            message=f"Validate attempt {attempt}",
            data={"attempt": attempt},
        )
        time.sleep(args.sleep)
        emit(
            run_id=run_id,
            job=JOB,
            stage="validate",
            status="done" if attempt == 1 else "failed",
            sequence=seq,
            message=f"Validate attempt {attempt} finished",
            error="" if attempt == 1 else "threshold not met on retry",
            data={"attempt": attempt},
        )
        print(f"[sample_retry] validate seq={seq} attempt={attempt}")

    print(f"[sample_retry] done — open dashboard and expand job; two validate rows (Seq 4 and 5)")


if __name__ == "__main__":
    main()
