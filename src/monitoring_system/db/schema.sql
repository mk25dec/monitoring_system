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

CREATE INDEX IF NOT EXISTS idx_events_run_ts ON events (run_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_job ON events (job);

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
