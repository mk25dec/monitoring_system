"""Stable event envelope — extend via ``data`` without breaking the platform."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from monitoring_system.status import status_bucket

class StageEnvelope(BaseModel):
    """Versioned envelope. Core fields are stable; ``data`` is free-form."""

    schema_version: int = 1
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: datetime = Field(default_factory=datetime.now)
    run_id: str
    job: str
    stage: str
    status: str
    sequence: int | None = None
    message: str | None = None
    error: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _legacy_module_field(cls, data: Any) -> Any:
        if isinstance(data, dict) and "module" in data and "job" not in data:
            data = {**data, "job": data["module"]}
        return data

    @model_validator(mode="before")
    @classmethod
    def _lift_message_error_from_data(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        extra = data.get("data")
        if not isinstance(extra, dict):
            return data
        out = dict(data)
        for key in ("message", "error"):
            if key in extra and out.get(key) in (None, ""):
                out[key] = extra.get(key)
        return out

    @field_validator("ts", mode="after")
    @classmethod
    def _naive_ts(cls, v: datetime) -> datetime:
        if v.tzinfo is not None:
            return v.replace(tzinfo=None)
        return v

    def to_redis_fields(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        payload["ts"] = self.ts.strftime("%Y-%m-%d %H:%M:%S")
        return {"body": json.dumps(payload, separators=(",", ":"))}

    @classmethod
    def from_redis_fields(cls, fields: dict[str, str | bytes]) -> StageEnvelope:
        raw = fields.get("body") or fields.get(b"body")
        if raw is None:
            raise ValueError("missing body field in stream entry")
        if isinstance(raw, bytes):
            raw = raw.decode()
        return cls.model_validate_json(raw)

    @property
    def ts_local_str(self) -> str:
        return self.ts.strftime("%Y-%m-%d %H:%M:%S")

    def merged_data(self) -> dict[str, Any]:
        """Payload persisted to SQLite (includes message / error / display fields)."""
        out = dict(self.data)
        if self.message is not None:
            out["message"] = self.message
        if self.error is not None:
            out["error"] = self.error
        out.setdefault("row_kind", "stage")
        out.setdefault("status_bucket", status_bucket(self.status))
        for key in ("progress_pct", "progress", "percent", "pct"):
            if key in out and "progress_pct" not in out:
                try:
                    num = float(out[key])
                except (TypeError, ValueError):
                    break
                if key == "progress" and 0 <= num <= 1:
                    num *= 100
                out["progress_pct"] = max(0.0, min(100.0, num))
                break
        return out
