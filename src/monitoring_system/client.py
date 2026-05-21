"""Producer SDK — one import, one line per stage update."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

import redis

from monitoring_system.config import Settings, load_settings
from monitoring_system.envelope import StageEnvelope

_SPOOL_DIR = Path("data/spool")


class StageClient:
    """Emit stage events to Redis Stream (with optional offline spool)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or load_settings()
        self._redis = redis.Redis.from_url(
            self._settings.redis.url,
            decode_responses=False,
        )
        self._stream = self._settings.redis.stream

    def emit(
        self,
        *,
        run_id: str,
        module: str,
        stage: str,
        status: str,
        data: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> str:
        envelope = StageEnvelope(
            run_id=run_id,
            module=module,
            stage=stage,
            status=status,
            data=data or {},
        )
        if event_id:
            envelope.event_id = event_id
        return self._publish(envelope)

    def _publish(self, envelope: StageEnvelope) -> str:
        fields = envelope.to_redis_fields()
        try:
            entry_id = self._redis.xadd(self._stream, fields)
            if isinstance(entry_id, bytes):
                entry_id = entry_id.decode()
            return envelope.event_id
        except redis.RedisError:
            self._spool(envelope)
            return envelope.event_id

    def _spool(self, envelope: StageEnvelope) -> None:
        _SPOOL_DIR.mkdir(parents=True, exist_ok=True)
        path = _SPOOL_DIR / f"{envelope.event_id}.json"
        path.write_text(
            json.dumps(envelope.model_dump(mode="json"), separators=(",", ":")),
            encoding="utf-8",
        )

    def flush_spool(self) -> int:
        """Retry spooled events when Redis is back. Returns count flushed."""
        if not _SPOOL_DIR.is_dir():
            return 0
        count = 0
        for path in sorted(_SPOOL_DIR.glob("*.json")):
            envelope = StageEnvelope.model_validate_json(path.read_text())
            try:
                self._redis.xadd(self._stream, envelope.to_redis_fields())
                path.unlink(missing_ok=True)
                count += 1
            except redis.RedisError:
                break
        return count

    @contextmanager
    def track(
        self,
        run_id: str,
        module: str,
        stage: str,
        *,
        data: dict[str, Any] | None = None,
        ok_status: str = "done",
        fail_status: str = "failed",
    ) -> Generator[dict[str, Any], None, None]:
        """Context manager: running → done/failed."""
        extra = dict(data or {})
        self.emit(
            run_id=run_id,
            module=module,
            stage=stage,
            status="running",
            data=extra,
        )
        try:
            yield extra
            self.emit(
                run_id=run_id,
                module=module,
                stage=stage,
                status=ok_status,
                data=extra,
            )
        except Exception as exc:
            extra["error"] = repr(exc)
            self.emit(
                run_id=run_id,
                module=module,
                stage=stage,
                status=fail_status,
                data=extra,
            )
            raise


_default_client: StageClient | None = None


def get_client() -> StageClient:
    global _default_client
    if _default_client is None:
        _default_client = StageClient()
    return _default_client


def emit(
    *,
    run_id: str,
    module: str,
    stage: str,
    status: str,
    data: dict[str, Any] | None = None,
) -> str:
    """Module-level shortcut: ``from monitoring_system import emit``."""
    return get_client().emit(
        run_id=run_id,
        module=module,
        stage=stage,
        status=status,
        data=data,
    )


def track(
    run_id: str,
    module: str,
    stage: str,
    **kwargs: Any,
):
    return get_client().track(run_id=run_id, module=module, stage=stage, **kwargs)
