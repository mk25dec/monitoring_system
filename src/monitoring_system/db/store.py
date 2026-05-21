"""SQLite persistence — core columns + JSON payload for extensibility."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from monitoring_system.db.job_summary import JOB_SEQUENCE, upsert_job_summary
from monitoring_system.envelope import StageEnvelope
from monitoring_system.status import is_running, is_terminal
from monitoring_system.timefmt import format_ts, parse_ts

_TABLES_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    job TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    sequence INTEGER,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS current_state (
    run_id TEXT NOT NULL,
    job TEXT NOT NULL,
    stage TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    status TEXT NOT NULL,
    ts TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    duration_sec REAL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, job, sequence)
);
"""

_VIEW_SQL = """
DROP VIEW IF EXISTS ui_dashboard;
CREATE VIEW ui_dashboard AS
SELECT
    run_id,
    job,
    stage,
    status,
    ts,
    sequence,
    started_at,
    ended_at,
    duration_sec,
    payload
FROM current_state
ORDER BY run_id, job, sequence;
"""

_MIGRATIONS = [
    "ALTER TABLE events ADD COLUMN sequence INTEGER",
    "ALTER TABLE current_state ADD COLUMN sequence INTEGER",
    "ALTER TABLE current_state ADD COLUMN started_at TEXT",
    "ALTER TABLE current_state ADD COLUMN ended_at TEXT",
    "ALTER TABLE current_state ADD COLUMN duration_sec REAL",
    "ALTER TABLE events RENAME COLUMN module TO job",
    "ALTER TABLE current_state RENAME COLUMN module TO job",
]


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _table_sql(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return (row[0] or "") if row else ""


def _pk_uses_sequence(conn: sqlite3.Connection) -> bool:
    sql = _table_sql(conn, "current_state").upper().replace(" ", "")
    return "PRIMARYKEY(RUN_ID,JOB,SEQUENCE)" in sql


def _migrate_current_state_sequence_pk(conn: sqlite3.Connection) -> None:
    if _pk_uses_sequence(conn):
        return
    if not _table_sql(conn, "current_state"):
        return
    conn.execute("DROP VIEW IF EXISTS ui_dashboard")
    conn.execute("DROP TABLE IF EXISTS current_state_new")
    conn.executescript(
        """
        CREATE TABLE current_state_new (
            run_id TEXT NOT NULL,
            job TEXT NOT NULL,
            stage TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            status TEXT NOT NULL,
            ts TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            started_at TEXT,
            ended_at TEXT,
            duration_sec REAL,
            payload TEXT NOT NULL,
            PRIMARY KEY (run_id, job, sequence)
        );
        INSERT INTO current_state_new (
            run_id, job, stage, sequence, status, ts, schema_version,
            started_at, ended_at, duration_sec, payload
        )
        SELECT
            run_id,
            job,
            stage,
            ROW_NUMBER() OVER (
                PARTITION BY run_id, job
                ORDER BY COALESCE(sequence, 2147483647), ts, stage
            ),
            status,
            ts,
            schema_version,
            started_at,
            ended_at,
            duration_sec,
            payload
        FROM current_state;
        DROP TABLE current_state;
        ALTER TABLE current_state_new RENAME TO current_state;
        """
    )


def _normalize_ts(value: str | None) -> str | None:
    if value is None:
        return None
    text = format_ts(str(value))
    return None if text == "—" else text


def _timing_from_events(
    events: list[tuple[str, str]],
) -> tuple[str | None, str | None, float | None]:
    started_at: str | None = None
    ended_at: str | None = None
    for status, ts in events:
        ts_norm = _normalize_ts(ts)
        if not ts_norm:
            continue
        if is_running(status) and not started_at:
            started_at = ts_norm
        if is_terminal(status):
            if not started_at:
                started_at = ts_norm
            ended_at = ts_norm
    duration_sec = _duration_between(started_at, ended_at)
    return started_at, ended_at, duration_sec


def backfill_job_summaries(db_path: Path) -> int:
    """Ensure every (run_id, job) with stages has a sequence=0 job row."""
    updated = 0
    with sqlite3.connect(db_path) as conn:
        keys = conn.execute(
            """
            SELECT DISTINCT run_id, job FROM current_state
            WHERE sequence > ?
            """,
            (JOB_SEQUENCE,),
        ).fetchall()
        for run_id, job in keys:
            upsert_job_summary(conn, run_id, job)
            updated += 1
        conn.commit()
    return updated


def backfill_timing(db_path: Path) -> int:
    """Recompute started_at / ended_at / duration_sec from events history."""
    updated = 0
    with sqlite3.connect(db_path) as conn:
        keys = conn.execute(
            "SELECT DISTINCT run_id, job, sequence FROM events WHERE sequence IS NOT NULL"
        ).fetchall()
        for run_id, job, sequence in keys:
            events = conn.execute(
                """
                SELECT status, ts FROM events
                WHERE run_id = ? AND job = ? AND sequence = ?
                ORDER BY ts ASC, rowid ASC
                """,
                (run_id, job, sequence),
            ).fetchall()
            started_at, ended_at, duration_sec = _timing_from_events(events)
            cur = conn.execute(
                """
                UPDATE current_state
                SET started_at = ?, ended_at = ?, duration_sec = ?
                WHERE run_id = ? AND job = ? AND sequence = ?
                """,
                (started_at, ended_at, duration_sec, run_id, job, sequence),
            )
            if cur.rowcount:
                updated += 1
            else:
                row = conn.execute(
                    """
                    SELECT stage, status, ts, schema_version, payload
                    FROM events
                    WHERE run_id = ? AND job = ? AND sequence = ?
                    ORDER BY ts DESC, rowid DESC
                    LIMIT 1
                    """,
                    (run_id, job, sequence),
                ).fetchone()
                if row and started_at:
                    conn.execute(
                        """
                        INSERT INTO current_state (
                            run_id, job, stage, sequence, status, ts, schema_version,
                            started_at, ended_at, duration_sec, payload
                        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            job,
                            row[0],
                            sequence,
                            row[1],
                            _normalize_ts(row[2]) or row[2],
                            started_at,
                            ended_at,
                            duration_sec,
                            row[4] or "{}",
                        ),
                    )
                    updated += 1
        conn.commit()
    return updated


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_TABLES_SQL)
        for stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
        # Legacy DB: table created with module column before job rename migration.
        if _column_exists(conn, "current_state", "module") and not _column_exists(
            conn, "current_state", "job"
        ):
            conn.execute("ALTER TABLE current_state RENAME COLUMN module TO job")
        if _column_exists(conn, "events", "module") and not _column_exists(conn, "events", "job"):
            conn.execute("ALTER TABLE events RENAME COLUMN module TO job")
        _migrate_current_state_sequence_pk(conn)
        conn.executescript(_VIEW_SQL)
        conn.commit()
    backfill_timing(db_path)
    backfill_job_summaries(db_path)


def _duration_between(start: str | None, end: str | None) -> float | None:
    s, e = parse_ts(start), parse_ts(end)
    if not s or not e:
        return None
    return max(0.0, (e - s).total_seconds())


def _resolve_sequence(envelope: StageEnvelope) -> int:
    if envelope.sequence is not None:
        seq = int(envelope.sequence)
        if seq == JOB_SEQUENCE:
            raise ValueError("sequence 0 is reserved for the job summary row; use 1, 2, … for stages")
        return seq
    return 1


def persist_event(db_path: Path, envelope: StageEnvelope) -> bool:
    """Insert event and upsert current_state. Returns False if duplicate event_id."""
    init_db(db_path)
    seq = _resolve_sequence(envelope)
    payload = json.dumps(envelope.merged_data(), separators=(",", ":"))
    ts = envelope.ts_local_str
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO events (
                event_id, ts, run_id, job, stage, status,
                schema_version, sequence, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                envelope.event_id,
                ts,
                envelope.run_id,
                envelope.job,
                envelope.stage,
                envelope.status,
                envelope.schema_version,
                seq,
                payload,
            ),
        )
        if cur.rowcount == 0:
            conn.commit()
            return False

        row = conn.execute(
            """
            SELECT started_at, ended_at FROM current_state
            WHERE run_id = ? AND job = ? AND sequence = ?
            """,
            (envelope.run_id, envelope.job, seq),
        ).fetchone()

        started_at = row[0] if row else None
        ended_at = row[1] if row else None

        if is_running(envelope.status) and not started_at:
            started_at = ts
        if is_terminal(envelope.status):
            if not started_at:
                started_at = ts
            ended_at = ts
        elif is_running(envelope.status):
            ended_at = None

        duration_sec = _duration_between(started_at, ended_at)

        conn.execute(
            """
            INSERT INTO current_state (
                run_id, job, stage, sequence, status, ts, schema_version,
                started_at, ended_at, duration_sec, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id, job, sequence) DO UPDATE SET
                stage = excluded.stage,
                status = excluded.status,
                ts = excluded.ts,
                schema_version = excluded.schema_version,
                started_at = COALESCE(current_state.started_at, excluded.started_at),
                ended_at = excluded.ended_at,
                duration_sec = excluded.duration_sec,
                payload = excluded.payload
            """,
            (
                envelope.run_id,
                envelope.job,
                envelope.stage,
                seq,
                envelope.status,
                ts,
                envelope.schema_version,
                started_at,
                ended_at,
                duration_sec,
                payload,
            ),
        )
        upsert_job_summary(conn, envelope.run_id, envelope.job)
        conn.commit()
    return True


def delete_run(db_path: Path, run_id: str) -> dict[str, int]:
    """Remove all events and current_state rows for one run_id."""
    with sqlite3.connect(db_path) as conn:
        events = conn.execute("DELETE FROM events WHERE run_id = ?", (run_id,)).rowcount
        state = conn.execute("DELETE FROM current_state WHERE run_id = ?", (run_id,)).rowcount
        conn.commit()
    return {"events": events, "current_state": state}


def clear_database(db_path: Path) -> dict[str, int]:
    """Remove all rows from events and current_state."""
    with sqlite3.connect(db_path) as conn:
        events = conn.execute("DELETE FROM events").rowcount
        state = conn.execute("DELETE FROM current_state").rowcount
        conn.commit()
    return {"events": events, "current_state": state}
