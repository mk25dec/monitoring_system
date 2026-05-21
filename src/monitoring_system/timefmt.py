"""Plain local timestamps and durations for the UI."""

from __future__ import annotations

import math
from datetime import datetime


def now_local_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_ts(value: str | None) -> str:
    """Show time without timezone (e.g. 2025-05-21 14:30:05)."""
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        return "—"
    raw = str(value).strip()
    if not raw:
        return "—"

    cleaned = raw.replace("T", " ")
    if "+" in cleaned:
        cleaned = cleaned.split("+", 1)[0].strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1].strip()
    if "." in cleaned:
        cleaned = cleaned.split(".", 1)[0]

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(cleaned[:19], fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return cleaned[:19] if len(cleaned) >= 19 else raw


def parse_ts(value: str | None) -> datetime | None:
    text = format_ts(value)
    if text == "—":
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if isinstance(seconds, float) and math.isnan(seconds):
        return "—"
    if seconds < 0:
        return "—"
    total = int(seconds)
    if total < 60:
        return f"{total} sec"
    minutes, sec = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} min {sec} sec"
    hours, rem = divmod(minutes, 60)
    return f"{hours} hr {rem} min"
