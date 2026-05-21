"""Job-level row (sequence=0) — aggregated when stages are persisted, not in the UI."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from monitoring_system.status import status_bucket
from monitoring_system.timefmt import format_duration, parse_ts

JOB_SEQUENCE = 0


def _parse_payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _progress_from_payload(payload: dict[str, Any]) -> float | None:
    for key in ("progress_pct", "progress", "percent", "pct"):
        if key not in payload:
            continue
        try:
            num = float(payload[key])
        except (TypeError, ValueError):
            continue
        if key == "progress" and 0 <= num <= 1:
            num *= 100
        return max(0.0, min(100.0, num))
    return None


def _overall_bucket(buckets: list[str]) -> str:
    s = set(buckets)
    if "failed" in s:
        return "failed"
    if "running" in s:
        return "running"
    if s <= {"success"} and s:
        return "success"
    return "other"


def _overall_status(bucket: str) -> str:
    if bucket == "failed":
        return "failed"
    if bucket == "running":
        return "running"
    if bucket == "success":
        return "done"
    return "other"


def upsert_job_summary(conn: sqlite3.Connection, run_id: str, job: str) -> None:
    """Recompute and upsert the synthetic job row (sequence=0) from stage rows."""
    rows = conn.execute(
        """
        SELECT sequence, stage, status, ts, started_at, ended_at, duration_sec, payload
        FROM current_state
        WHERE run_id = ? AND job = ? AND sequence > ?
        ORDER BY sequence, stage
        """,
        (run_id, job, JOB_SEQUENCE),
    ).fetchall()
    if not rows:
        conn.execute(
            "DELETE FROM current_state WHERE run_id = ? AND job = ? AND sequence = ?",
            (run_id, job, JOB_SEQUENCE),
        )
        return

    n = len(rows)
    buckets = [status_bucket(str(r[2])) for r in rows]
    overall_bucket = _overall_bucket(buckets)
    status = _overall_status(overall_bucket)

    starts = [parse_ts(r[4]) for r in rows if r[4]]
    ends = [parse_ts(r[5]) for r in rows if r[5]]
    started_at = min(starts).strftime("%Y-%m-%d %H:%M:%S") if starts else None
    if ends:
        ended_at = max(ends).strftime("%Y-%m-%d %H:%M:%S")
    elif "running" in buckets:
        ended_at = None
    else:
        ended_at = None

    durations = [r[6] for r in rows if r[6] is not None]
    if durations:
        duration_sec = float(sum(durations))
    elif starts and ends:
        duration_sec = max(0.0, (max(ends) - min(starts)).total_seconds())
    elif starts and overall_bucket == "running":
        duration_sec = max(0.0, (datetime.now() - min(starts)).total_seconds())
    else:
        duration_sec = None

    progress_vals = []
    for row in rows:
        pct = _progress_from_payload(_parse_payload(row[7]))
        if pct is not None:
            progress_vals.append(pct)
    progress_pct = int(round(sum(progress_vals) / len(progress_vals))) if progress_vals else 0

    failed_rows = [r for r in rows if status_bucket(str(r[2])) == "failed"]
    job_message = ""
    job_error = ""
    if failed_rows:
        fp = _parse_payload(failed_rows[0][7])
        job_error = str(fp.get("error") or "")
        job_message = str(fp.get("message") or "")
    else:
        fp = _parse_payload(rows[0][7])
        job_message = str(fp.get("message") or "")

    latest_ts = max(str(r[3]) for r in rows)
    payload = json.dumps(
        {
            "row_kind": "job",
            "progress_pct": progress_pct,
            "status_bucket": overall_bucket,
            "step_count": n,
            "message": job_message,
            "error": job_error,
            "display_ended": "in progress" if ended_at is None and overall_bucket == "running" else None,
        },
        separators=(",", ":"),
    )

    conn.execute(
        """
        INSERT INTO current_state (
            run_id, job, stage, sequence, status, ts, schema_version,
            started_at, ended_at, duration_sec, payload
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        ON CONFLICT (run_id, job, sequence) DO UPDATE SET
            stage = excluded.stage,
            status = excluded.status,
            ts = excluded.ts,
            started_at = excluded.started_at,
            ended_at = excluded.ended_at,
            duration_sec = excluded.duration_sec,
            payload = excluded.payload
        """,
        (
            run_id,
            job,
            f"({n} step{'s' if n != 1 else ''})",
            JOB_SEQUENCE,
            status,
            latest_ts,
            started_at,
            ended_at,
            duration_sec,
            payload,
        ),
    )
