"""SQLite persistence — core columns + JSON payload for extensibility."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from monitoring_system.envelope import StageEnvelope

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def persist_event(db_path: Path, envelope: StageEnvelope) -> bool:
    """Insert event and upsert current_state. Returns False if duplicate event_id."""
    payload = json.dumps(envelope.data, separators=(",", ":"))
    ts = envelope.ts.isoformat()
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO events (
                event_id, ts, run_id, module, stage, status,
                schema_version, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                envelope.event_id,
                ts,
                envelope.run_id,
                envelope.module,
                envelope.stage,
                envelope.status,
                envelope.schema_version,
                payload,
            ),
        )
        if cur.rowcount == 0:
            conn.commit()
            return False
        conn.execute(
            """
            INSERT INTO current_state (
                run_id, module, stage, status, ts, schema_version, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id, module, stage) DO UPDATE SET
                status = excluded.status,
                ts = excluded.ts,
                schema_version = excluded.schema_version,
                payload = excluded.payload
            """,
            (
                envelope.run_id,
                envelope.module,
                envelope.stage,
                envelope.status,
                ts,
                envelope.schema_version,
                payload,
            ),
        )
        conn.commit()
    return True
