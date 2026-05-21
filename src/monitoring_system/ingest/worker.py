"""Consume Redis Stream, persist to SQLite, ACK only after commit."""

from __future__ import annotations

import logging
import signal
import sys
import time

import redis

from monitoring_system.config import load_settings
from monitoring_system.db import init_db, persist_event
from monitoring_system.envelope import StageEnvelope

logger = logging.getLogger(__name__)


def _ensure_consumer_group(r: redis.Redis, stream: str, group: str) -> None:
    try:
        r.xgroup_create(stream, group, id="0", mkstream=True)
        logger.info("created consumer group %s on %s", group, stream)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def _decode_entry(entry_id: str | bytes, fields: dict) -> tuple[str, StageEnvelope]:
    eid = entry_id.decode() if isinstance(entry_id, bytes) else entry_id
    decoded = {
        (k.decode() if isinstance(k, bytes) else k): (
            v.decode() if isinstance(v, bytes) else v
        )
        for k, v in fields.items()
    }
    return eid, StageEnvelope.from_redis_fields(decoded)


def run_loop() -> None:
    settings = load_settings()
    db_path = settings.sqlite.resolved_path()
    init_db(db_path)

    r = redis.Redis.from_url(settings.redis.url, decode_responses=False)
    stream = settings.redis.stream
    group = settings.redis.consumer_group
    consumer = settings.redis.consumer_name
    batch = settings.ingest.batch_size
    block_ms = settings.ingest.block_ms
    claim_idle = settings.ingest.claim_idle_ms

    _ensure_consumer_group(r, stream, group)
    logger.info("ingest worker %s listening on %s → %s", consumer, stream, db_path)

    stop = False

    def _handle_signal(*_args: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not stop:
        _claim_pending(r, stream, group, consumer, db_path, claim_idle, batch)
        messages = r.xreadgroup(
            group,
            consumer,
            {stream: ">"},
            count=batch,
            block=block_ms,
        )
        if not messages:
            continue
        for _stream_name, entries in messages:
            for entry_id, fields in entries:
                try:
                    eid, envelope = _decode_entry(entry_id, fields)
                    persist_event(db_path, envelope)
                    r.xack(stream, group, entry_id)
                except Exception:
                    logger.exception("failed entry %s", entry_id)
        time.sleep(0)


def _claim_pending(
    r: redis.Redis,
    stream: str,
    group: str,
    consumer: str,
    db_path,
    min_idle_ms: int,
    batch: int,
) -> None:
    """Replay stale pending messages (crash recovery)."""
    start_id = "0-0"
    while True:
        pending = r.xautoclaim(
            stream,
            group,
            consumer,
            min_idle_time=min_idle_ms,
            start_id=start_id,
            count=batch,
        )
        if not pending or len(pending) < 2:
            break
        _next_start, entries, *_rest = pending
        if not entries:
            break
        for entry_id, fields in entries:
            try:
                _eid, envelope = _decode_entry(entry_id, fields)
                persist_event(db_path, envelope)
                r.xack(stream, group, entry_id)
            except Exception:
                logger.exception("failed pending entry %s", entry_id)
        start_id = _next_start.decode() if isinstance(_next_start, bytes) else _next_start


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        run_loop()
    except redis.ConnectionError as exc:
        logger.error("redis not available: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
