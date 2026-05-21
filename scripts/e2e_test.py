#!/usr/bin/env python3
"""End-to-end smoke test for monitoring_system."""

import sqlite3
import sys
import uuid

import redis

from monitoring_system import emit
from monitoring_system.config import load_settings
from monitoring_system.db import init_db, persist_event
from monitoring_system.ingest.worker import _decode_entry, _ensure_consumer_group


def main() -> int:
    settings = load_settings()
    db_path = settings.sqlite.resolved_path()
    run_id = f"e2e-{uuid.uuid4().hex[:8]}"

    print("1. Redis...")
    r = redis.Redis.from_url(settings.redis.url)
    if not r.ping():
        print("FAIL: Redis not running")
        return 1
    print("   OK")

    print("2. DB migrate (module -> job)...")
    try:
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            cols = [c[1] for c in conn.execute("PRAGMA table_info(current_state)").fetchall()]
        if "job" not in cols:
            print(f"FAIL: missing job column, have {cols}")
            return 1
        print(f"   OK columns include job")
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    print("3. Emit event...")
    eid = emit(
        run_id=run_id,
        job="e2e.test",
        stage="smoke",
        status="done",
        sequence=1,
        data={"progress": 100},
    )
    print(f"   OK event_id={eid}")

    print("4. Ingest from stream...")
    stream = settings.redis.stream
    group = settings.redis.consumer_group
    _ensure_consumer_group(r, stream, group)
    messages = r.xreadgroup(group, "e2e-test", {stream: ">"}, count=50, block=1000)
    ingested = 0
    if messages:
        for _s, entries in messages:
            for entry_id, fields in entries:
                try:
                    _eid, envelope = _decode_entry(entry_id, fields)
                    persist_event(db_path, envelope)
                    r.xack(stream, group, entry_id)
                    ingested += 1
                except Exception as exc:
                    print(f"   WARN: {exc}")
    print(f"   ingested {ingested} message(s)")

    print("5. Verify row in ui_dashboard...")
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT run_id, job, stage, status FROM ui_dashboard WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    if not row:
        print("FAIL: row not in ui_dashboard")
        return 1
    print(f"   OK {row}")

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
