from pathlib import Path

import sqlite3

from monitoring_system.db.store import backfill_timing, init_db, persist_event
from monitoring_system.envelope import StageEnvelope


def test_backfill_timing_from_events(tmp_path: Path) -> None:
    db = tmp_path / "test.db"
    init_db(db)

    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO events (event_id, ts, run_id, job, stage, status, schema_version, sequence, payload)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, '{}')
            """,
            ("e1", "2026-05-21T10:00:00+00:00", "r1", "job.a", "step1", "running"),
        )
        conn.execute(
            """
            INSERT INTO events (event_id, ts, run_id, job, stage, status, schema_version, sequence, payload)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, '{}')
            """,
            ("e2", "2026-05-21T10:00:05+00:00", "r1", "job.a", "step1", "done"),
        )
        conn.execute(
            """
            INSERT INTO current_state (
                run_id, job, stage, sequence, status, ts, schema_version,
                started_at, ended_at, duration_sec, payload
            ) VALUES (?, ?, ?, 1, 'done', ?, 1, NULL, NULL, NULL, '{}')
            """,
            ("r1", "job.a", "step1", "2026-05-21 10:00:05"),
        )
        conn.commit()

    assert backfill_timing(db) >= 1
    row = sqlite3.connect(db).execute(
        "SELECT started_at, ended_at, duration_sec FROM current_state WHERE sequence = 1"
    ).fetchone()
    assert row[0] == "2026-05-21 10:00:00"
    assert row[1] == "2026-05-21 10:00:05"
    assert row[2] == 5.0


def test_persist_sets_timing(tmp_path: Path) -> None:
    db = tmp_path / "persist.db"
    init_db(db)
    persist_event(
        db,
        StageEnvelope(run_id="r2", job="j", stage="s", status="running", sequence=1),
    )
    persist_event(
        db,
        StageEnvelope(run_id="r2", job="j", stage="s", status="done", sequence=1),
    )
    row = sqlite3.connect(db).execute(
        "SELECT started_at, ended_at, duration_sec FROM current_state"
    ).fetchone()
    assert row[0] is not None
    assert row[1] is not None
    assert row[2] is not None


def test_same_stage_different_sequence(tmp_path: Path) -> None:
    db = tmp_path / "repeat.db"
    init_db(db)
    persist_event(
        db,
        StageEnvelope(
            run_id="r3",
            job="j",
            stage="validate",
            status="done",
            sequence=1,
            message="first ok",
        ),
    )
    persist_event(
        db,
        StageEnvelope(
            run_id="r3",
            job="j",
            stage="validate",
            status="failed",
            sequence=2,
            message="second failed",
            error="boom",
        ),
    )
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT sequence, stage, payload FROM current_state WHERE run_id = 'r3' ORDER BY sequence"
        ).fetchall()
    assert len(rows) == 3
    assert rows[0][0] == 0
    assert rows[1][0] == 1
    assert rows[2][0] == 2
    assert "boom" in rows[2][2]


def test_job_summary_row(tmp_path: Path) -> None:
    db = tmp_path / "job_sum.db"
    init_db(db)
    for seq, stage, status, progress in (
        (1, "package", "done", 100),
        (2, "upload", "done", 100),
        (3, "validate", "failed", 60),
    ):
        persist_event(
            db,
            StageEnvelope(
                run_id="export-abc",
                job="samples.export",
                stage=stage,
                status=status,
                sequence=seq,
                message=f"{stage} msg",
                error="checksum mismatch" if status == "failed" else None,
                data={"progress": progress},
            ),
        )
    with sqlite3.connect(db) as conn:
        job = conn.execute(
            """
            SELECT sequence, stage, status, duration_sec, payload
            FROM current_state
            WHERE run_id = 'export-abc' AND sequence = 0
            """
        ).fetchone()
        stage_count = conn.execute(
            "SELECT COUNT(*) FROM current_state WHERE run_id = 'export-abc' AND sequence > 0"
        ).fetchone()[0]
    assert stage_count == 3
    assert job is not None
    assert job[0] == 0
    assert job[1] == "(3 steps)"
    assert job[2] == "failed"
    payload = __import__("json").loads(job[4])
    assert payload["progress_pct"] == 87
    assert payload["row_kind"] == "job"
    assert payload["error"] == "checksum mismatch"
