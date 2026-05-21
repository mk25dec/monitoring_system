"""Stable event envelope — extend via ``data`` without breaking the platform."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class StageEnvelope(BaseModel):
    """Versioned envelope. Core fields are stable; ``data`` is free-form."""

    schema_version: int = 1
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str
    module: str
    stage: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)

    def to_redis_fields(self) -> dict[str, str]:
        payload = self.model_dump(mode="json")
        return {"body": json.dumps(payload, separators=(",", ":"))}

    @classmethod
    def from_redis_fields(cls, fields: dict[str, str | bytes]) -> StageEnvelope:
        raw = fields.get("body") or fields.get(b"body")
        if raw is None:
            raise ValueError("missing body field in stream entry")
        if isinstance(raw, bytes):
            raw = raw.decode()
        return cls.model_validate_json(raw)
