from datetime import date, datetime

from src.build_foundation_marts import (
    daypart_for,
    interval_time_metadata,
    is_operating_interval,
    load_config,
)


def test_operating_hours_respect_source_schedule() -> None:
    staffed = load_config()["scope"]["agent_staffed_hours"]

    assert is_operating_interval(date(1999, 1, 1), "1330", staffed)
    assert not is_operating_interval(date(1999, 1, 1), "1400", staffed)
    assert not is_operating_interval(date(1999, 1, 2), "1930", staffed)
    assert is_operating_interval(date(1999, 1, 2), "2000", staffed)
    assert not is_operating_interval(date(1999, 1, 3), "0630", staffed)
    assert is_operating_interval(date(1999, 1, 3), "0700", staffed)


def test_every_interval_maps_to_exactly_one_daypart() -> None:
    dayparts = load_config()["scope"]["dayparts"]

    mapped = [
        daypart_for(f"{slot // 2:02d}{(slot % 2) * 30:02d}", dayparts)
        for slot in range(48)
    ]

    assert len(mapped) == 48
    assert set(mapped) == {"overnight", "morning", "afternoon", "evening"}


def test_dst_wall_clock_anomalies_are_explicit() -> None:
    statuses = []
    for month in range(1, 13):
        for day_number in range(1, 32):
            try:
                day = date(1999, month, day_number)
            except ValueError:
                continue
            for slot in range(48):
                metadata = interval_time_metadata(
                    day, f"{slot // 2:02d}{(slot % 2) * 30:02d}"
                )
                statuses.append(metadata["dst_status"])

    assert statuses.count("ambiguous") == 2
    assert statuses.count("nonexistent") == 2
    assert statuses.count("ends_ambiguous") == 1
    assert statuses.count("ends_nonexistent") == 1


def test_normal_interval_has_unambiguous_utc_boundaries() -> None:
    metadata = interval_time_metadata(date(1999, 1, 1), "1200")

    assert metadata["dst_status"] == "normal"
    assert metadata["actual_seconds"] == 1800
    assert datetime.fromisoformat(metadata["start_utc"]).tzinfo is not None
    assert datetime.fromisoformat(metadata["end_utc"]).tzinfo is not None
