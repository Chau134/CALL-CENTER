"""Validate P0 foundation marts and cross-grain reconciliation."""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter
from pathlib import Path

try:
    from .build_foundation_marts import OUTPUT_DIR, REPORT_DIR
    from .transform_calls import SERVICE_TYPE_LABELS, sha256
except ImportError:  # Support direct execution.
    from build_foundation_marts import OUTPUT_DIR, REPORT_DIR
    from transform_calls import SERVICE_TYPE_LABELS, sha256


REPORT_PATH = REPORT_DIR / "foundation_marts_reconciliation.json"
BLOCKED_COLUMNS = {"customer_id", "server", "raw_agent_label"}


def rows(filename: str):
    path = OUTPUT_DIR / filename
    with gzip.open(path, "rt", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        assert reader.fieldnames is not None
        assert not (set(reader.fieldnames) & BLOCKED_COLUMNS)
        yield from reader


def validate_dimensions() -> None:
    dates = list(rows("dim_date.csv.gz"))
    assert len(dates) == 365
    assert len({row["date_key"] for row in dates}) == 365
    assert dates[0]["calendar_date"] == "1999-01-01"
    assert dates[-1]["calendar_date"] == "1999-12-31"
    assert all(row["data_origin"] == "derived" for row in dates)
    assert all(
        row["holiday_data_origin"] in {"", "external_reference"} for row in dates
    )

    intervals = list(rows("dim_time_interval.csv.gz"))
    assert len(intervals) == 48
    assert {int(row["interval_number"]) for row in intervals} == set(range(48))
    assert {row["minute_number"] for row in intervals} == {"0", "30"}
    assert all(row["daypart"] for row in intervals)

    queues = list(rows("dim_queue.csv.gz"))
    assert len(queues) == 1
    assert queues[0]["queue_id"] == "INBOUND_SUPPORT"
    assert queues[0]["data_origin"] == "project_assumption"

    services = list(rows("dim_service_type.csv.gz"))
    assert len(services) == len(SERVICE_TYPE_LABELS)
    assert {row["service_type_code"] for row in services} == set(
        SERVICE_TYPE_LABELS
    )


def validate_facts() -> Counter[str]:
    queue_aggregates: dict[tuple[str, str], Counter[str]] = {}
    queue_keys: set[tuple[str, str, str]] = set()
    totals: Counter[str] = Counter()
    valid_statuses = {
        "observed_with_calls",
        "observed_excluded_only",
        "zero_filled_operating",
        "zero_filled_closed",
        "data_gap",
    }
    for row in rows("fact_queue_interval_complete.csv.gz"):
        key = (row["date_key"], row["interval_key"], row["queue_id"])
        assert key not in queue_keys
        queue_keys.add(key)
        offered = int(row["offered_calls"])
        agent_demand = int(row["agent_demand_calls"])
        answered = int(row["answered_calls"])
        abandoned = int(row["abandoned_calls"])
        excluded = int(row["excluded_record_count"])
        quarantine = int(row["quarantine_record_count"])
        raw = int(row["raw_record_count"])
        assert offered == answered + abandoned
        assert agent_demand == answered + int(row["queue_abandoned_calls"])
        assert abandoned == int(row["queue_abandoned_calls"]) + int(
            row["vru_abandoned_calls"]
        )
        assert raw == offered + excluded + quarantine
        assert int(row["service_level_denominator"]) == (
            offered - int(row["short_abandon_calls"])
        )
        assert row["coverage_status"] in valid_statuses
        assert row["interval_coverage_verified"] == "true"
        if row["coverage_status"].startswith("zero_filled"):
            assert offered == 0 and raw == 0 and row["zero_fill_reason"]
        if row["dst_status"] != "normal":
            assert row["interval_start_utc"] == "" or row[
                "interval_end_utc"
            ] == ""
        queue_aggregates[(row["date_key"], row["interval_key"])] = Counter(
            {
                "offered": offered,
                "answered": answered,
                "abandoned": abandoned,
                "agent_demand": agent_demand,
            }
        )
        totals["queue_rows"] += 1
        totals["offered"] += offered
        totals["agent_demand"] += agent_demand
        totals["raw"] += raw
        totals["excluded"] += excluded
        totals["quarantine"] += quarantine

    assert totals["queue_rows"] == 17_520
    assert totals["offered"] == 440_844
    assert totals["raw"] == 444_448
    assert totals["excluded"] == 3_599
    assert totals["quarantine"] == 5

    service_keys: set[tuple[str, str, str]] = set()
    service_aggregates: dict[tuple[str, str], Counter[str]] = {}
    for row in rows("fact_service_type_interval.csv.gz"):
        key = (
            row["date_key"],
            row["interval_key"],
            row["service_type_code"],
        )
        assert key not in service_keys
        service_keys.add(key)
        grain = (row["date_key"], row["interval_key"])
        bucket = service_aggregates.setdefault(grain, Counter())
        bucket["offered"] += int(row["offered_calls"])
        bucket["agent_demand"] += int(row["agent_demand_calls"])
        bucket["answered"] += int(row["answered_calls"])
        bucket["abandoned"] += int(row["abandoned_calls"])
        totals["service_rows"] += 1
        totals["service_offered"] += int(row["offered_calls"])
        totals["service_agent_demand"] += int(row["agent_demand_calls"])

    assert totals["service_rows"] == 17_520 * len(SERVICE_TYPE_LABELS)
    assert totals["service_offered"] == totals["offered"]
    assert totals["service_agent_demand"] == totals["agent_demand"]
    assert service_aggregates == queue_aggregates
    return totals


def validate_checksums() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    for filename, metadata in report["outputs"].items():
        assert sha256(OUTPUT_DIR / filename) == metadata["sha256"]


def main() -> None:
    validate_dimensions()
    totals = validate_facts()
    validate_checksums()
    print("Foundation mart validation passed")
    print(
        f"Dimensions: date=365, time=48, queue=1, "
        f"service_type={len(SERVICE_TYPE_LABELS)}"
    )
    print(
        f"Facts: queue={totals['queue_rows']:,}, "
        f"service={totals['service_rows']:,}, offered={totals['offered']:,}"
    )
    print(
        f"Raw={totals['raw']:,}, excluded={totals['excluded']:,}, "
        f"quarantine={totals['quarantine']:,}; cross-grain reconciliation passed"
    )


if __name__ == "__main__":
    main()
