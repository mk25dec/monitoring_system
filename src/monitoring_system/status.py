"""Shared status groups for ingest and dashboard."""

SUCCESS_STATUSES = frozenset({"done", "completed", "success", "ok", "passed"})
FAILED_STATUSES = frozenset({"failed", "error", "failure", "crashed", "cancelled"})
RUNNING_STATUSES = frozenset({"running", "in_progress", "processing", "started", "pending"})


def is_terminal(status: str) -> bool:
    s = str(status).lower().strip()
    return s in SUCCESS_STATUSES or s in FAILED_STATUSES


def is_running(status: str) -> bool:
    return str(status).lower().strip() in RUNNING_STATUSES


def status_bucket(status: str) -> str:
    s = str(status).lower().strip()
    if s in SUCCESS_STATUSES:
        return "success"
    if s in FAILED_STATUSES:
        return "failed"
    if s in RUNNING_STATUSES:
        return "running"
    return "other"
