from monitoring_system.envelope import StageEnvelope


def test_envelope_roundtrip_redis_fields():
    env = StageEnvelope(
        run_id="r1",
        job="my.job",
        stage="load",
        status="running",
        sequence=2,
        message="loading",
        error="",
        data={"extra": 1},
    )
    restored = StageEnvelope.from_redis_fields(env.to_redis_fields())
    assert restored.run_id == "r1"
    assert restored.sequence == 2
    assert restored.message == "loading"
    assert restored.data["extra"] == 1
    assert "+" not in restored.to_redis_fields()["body"]


def test_merged_data_includes_message_error():
    env = StageEnvelope(
        run_id="r1",
        job="j",
        stage="s",
        status="failed",
        sequence=1,
        message="Step failed",
        error="disk full",
        data={"progress": 10},
    )
    merged = env.merged_data()
    assert merged["message"] == "Step failed"
    assert merged["error"] == "disk full"
    assert merged["progress"] == 10
