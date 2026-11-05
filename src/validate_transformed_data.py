"""Validate ETL outputs without exposing customer IDs or raw agent labels."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "data" / "interim" / "technion"
REPORT_PATH = PROJECT_ROOT / "reports" / "data_quality" / "etl_reconciliation.json"
BASELINE_PATH = PROJECT_ROOT / "reports" / "data_quality" / "raw_baseline.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "technion" / "AnonymousBank"
BLOCKED_COLUMNS = {"customer_id", "server"}
AGENT_ID_PATTERN = re.compile(r"^AGENT_\d{3}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        assert reader.fieldnames is not None
        assert not (BLOCKED_COLUMNS & set(reader.fieldnames)), (
            f"PII/raw label column found in {path.name}"
        )
        yield from reader


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    summary = report["summary"]
    all_keys: set[str] = set()
    clean_count = 0

    for row in rows(OUTPUT_DIR / "calls_clean.csv.gz"):
        clean_count += 1
        key = row["source_call_key"]
        assert key and key not in all_keys, f"Duplicate source_call_key: {key}"
        all_keys.add(key)
        assert row["call_status"] in {"answered", "abandoned"}
        interval = datetime.fromisoformat(row["interval_start"])
        assert interval.minute in {0, 30} and interval.second == 0
        assert int(row["wait_seconds"]) >= 0
        assert int(row["service_seconds"]) >= 0
        if row["vru_seconds"]:
            assert int(row["vru_seconds"]) >= 0
        if row["agent_id"]:
            assert AGENT_ID_PATTERN.fullmatch(row["agent_id"])

    routed_counts = {"clean": clean_count}
    for stream in ("excluded", "quarantine"):
        count = 0
        for row in rows(OUTPUT_DIR / f"calls_{stream}.csv.gz"):
            count += 1
            key = row["source_call_key"]
            if key:
                assert key not in all_keys, f"Duplicate source_call_key: {key}"
                all_keys.add(key)
        routed_counts[stream] = count

    interval_rows = 0
    interval_offered = 0
    for row in rows(OUTPUT_DIR / "calls_interval_30m.csv.gz"):
        interval_rows += 1
        offered = int(row["offered_calls"])
        answered = int(row["answered_calls"])
        abandoned = int(row["abandoned_calls"])
        assert offered == answered + abandoned
        assert int(row["service_level_denominator"]) == (
            offered - int(row["short_abandon_calls"])
        )
        interval = datetime.fromisoformat(row["interval_start"])
        assert interval.minute in {0, 30} and interval.second == 0
        interval_offered += offered

    assert routed_counts["clean"] == summary["clean_rows"]
    assert routed_counts["excluded"] == summary["excluded_rows"]
    assert routed_counts["quarantine"] == summary["quarantine_rows"]
    assert sum(routed_counts.values()) == summary["raw_rows"]
    assert interval_rows == summary["interval_rows"]
    assert interval_offered == clean_count == summary["interval_offered_calls"]

    for filename, metadata in report["outputs"].items():
        assert sha256(OUTPUT_DIR / filename) == metadata["sha256"], (
            f"Checksum mismatch: {filename}"
        )
    for metadata in baseline["files"]:
        raw_path = RAW_DIR / metadata["file_name"]
        assert raw_path.stat().st_size == metadata["size_bytes"], (
            f"Raw size changed: {raw_path.name}"
        )
        assert sha256(raw_path) == metadata["sha256"], (
            f"Raw checksum changed: {raw_path.name}"
        )

    print("ETL output validation passed")
    print(
        f"Rows: raw={summary['raw_rows']:,}, clean={clean_count:,}, "
        f"excluded={routed_counts['excluded']:,}, "
        f"quarantine={routed_counts['quarantine']:,}"
    )
    print(
        f"30-minute intervals={interval_rows:,}; "
        f"offered calls={interval_offered:,}"
    )
    print(
        "Raw files unchanged; privacy columns absent; keys, durations, "
        "intervals, and checksums valid"
    )


if __name__ == "__main__":
    main()
