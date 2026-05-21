from monitoring_system.timefmt import format_duration, format_ts


def test_format_ts_strips_timezone():
    assert format_ts("2025-05-21T14:30:05+00:00") == "2025-05-21 14:30:05"
    assert format_ts("2025-05-21 14:30:05") == "2025-05-21 14:30:05"


def test_format_duration_readable():
    assert format_duration(45) == "45 sec"
    assert format_duration(125) == "2 min 5 sec"


def test_format_duration_nan():
    assert format_duration(float("nan")) == "—"
    assert format_duration(None) == "—"
