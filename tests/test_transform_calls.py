from datetime import date, datetime, timedelta

from src.transform_calls import (
    SOURCE_TIMEZONE,
    parse_source_date,
    parse_source_parts,
    relative_event,
)


def test_repairs_merged_priority_and_service_type() -> None:
    malformed = "\t".join(
        [
            "AA0101",
            "33116",
            "0",
            "2 PS",
            "990101",
            "0:00:31",
            "0:00:36",
            "5",
            "0:00:36",
            "0:03:09",
            "153",
            "HANG",
            "0:00:00",
            "0:00:00",
            "0",
            "NO_SERVER",
        ]
    )

    fields, repairs, original_count = parse_source_parts(malformed)

    assert original_count == 16
    assert fields is not None and len(fields) == 17
    assert fields[3:5] == ["2", "PS"]
    assert repairs == ["split_merged_priority_service_type"]


def test_unrepairable_field_count_is_rejected() -> None:
    fields, repairs, original_count = parse_source_parts("a\tb\tc")

    assert fields is None
    assert repairs == []
    assert original_count == 3


def test_source_date_is_forced_to_twentieth_century() -> None:
    assert parse_source_date("990101") == date(1999, 1, 1)


def test_small_backward_clock_skew_is_not_treated_as_next_day() -> None:
    previous = datetime(1999, 1, 1, 10, 0, 1, tzinfo=SOURCE_TIMEZONE)

    event, flag = relative_event(date(1999, 1, 1), "10:00:00", previous, 3600)

    assert event == previous - timedelta(seconds=1)
    assert flag == "minor_clock_skew"

