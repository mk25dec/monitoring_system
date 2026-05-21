PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    module TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_run_ts ON events (run_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_module ON events (module);

CREATE TABLE IF NOT EXISTS current_state (
    run_id TEXT NOT NULL,
    module TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    ts TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY (run_id, module, stage)
);

CREATE VIEW IF NOT EXISTS ui_dashboard AS
SELECT
    run_id,
    module,
    stage,
    status,
    ts,
    payload
FROM current_state
ORDER BY run_id, module, stage;
