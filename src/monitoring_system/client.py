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
        self._seq_counters: dict[tuple[str, str], int] = {}

    def next_sequence(self, run_id: str, job: str) -> int:
        """Next step number for this run + job (1, 2, 3, …)."""
        key = (run_id, job)
        n = self._seq_counters.get(key, 0) + 1
        self._seq_counters[key] = n
        return n

    def _resolve_sequence(self, run_id: str, job: str, sequence: int | None) -> int:
        key = (run_id, job)
        if sequence is not None:
            self._seq_counters[key] = max(self._seq_counters.get(key, 0), sequence)
            return sequence
        return self.next_sequence(run_id, job)

    def emit(
        self,
        *,
        run_id: str,
        job: str,
        stage: str,
        status: str,
        sequence: int | None = None,
        message: str | None = None,
        error: str | None = None,
        data: dict[str, Any] | None = None,
        event_id: str | None = None,
        module: str | None = None,  # deprecated alias for job
    ) -> str:
        seq = self._resolve_sequence(run_id, job, sequence)
        envelope = StageEnvelope(
            run_id=run_id,
            job=job or (module or ""),
            stage=stage,
            status=status,
            sequence=seq,
            message=message,
            error=error,
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
        body = envelope.model_dump(mode="json")
        body["ts"] = envelope.ts_local_str
        path.write_text(
            json.dumps(body, separators=(",", ":")),
            encoding="utf-8",
        )

    def flush_spool(self) -> int:
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
        job: str,
        stage: str,
        *,
        sequence: int | None = None,
        message: str | None = None,
        data: dict[str, Any] | None = None,
        ok_status: str = "done",
        fail_status: str = "failed",
        module: str | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        job_name = job or (module or "")
        seq = self._resolve_sequence(run_id, job_name, sequence)
        extra = dict(data or {})
        start_msg = message or f"Starting {stage}"
        self.emit(
            run_id=run_id,
            job=job_name,
            stage=stage,
            status="running",
            sequence=seq,
            message=start_msg,
            data=extra,
        )
        try:
            yield extra
            self.emit(
                run_id=run_id,
                job=job_name,
                stage=stage,
                status=ok_status,
                sequence=seq,
                message=message or f"{stage} completed",
                data=extra,
            )
        except Exception as exc:
            err_text = str(exc) or repr(exc)
            self.emit(
                run_id=run_id,
                job=job_name,
                stage=stage,
                status=fail_status,
                sequence=seq,
                message=message or f"{stage} failed",
                error=err_text,
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
    job: str,
    stage: str,
    status: str,
    sequence: int | None = None,
    message: str | None = None,
    error: str | None = None,
    data: dict[str, Any] | None = None,
    module: str | None = None,
) -> str:
    return get_client().emit(
        run_id=run_id,
        job=job,
        stage=stage,
        status=status,
        sequence=sequence,
        message=message,
        error=error,
        data=data,
        module=module,
    )


def track(run_id: str, job: str, stage: str, **kwargs: Any):
    return get_client().track(run_id=run_id, job=job, stage=stage, **kwargs)


def next_sequence(run_id: str, job: str) -> int:
    return get_client().next_sequence(run_id, job)
