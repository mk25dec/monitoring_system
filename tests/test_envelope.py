from monitoring_system.envelope import StageEnvelope


def test_envelope_roundtrip_redis_fields():
    env = StageEnvelope(
        run_id="r1",
        module="mod.a",
        stage="load",
        status="running",
        data={"extra": 1},
    )
    restored = StageEnvelope.from_redis_fields(env.to_redis_fields())
    assert restored.run_id == "r1"
    assert restored.data["extra"] == 1
