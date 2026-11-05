"""Transform Technion call records into clean, excluded, and quarantine streams.

The raw files are never modified. Processed outputs suppress customer IDs and
raw agent labels. Every input row is reconciled into exactly one output stream.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "technion" / "AnonymousBank"
OUTPUT_DIR = PROJECT_ROOT / "data" / "interim" / "technion"
REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"
TIMEZONE_NAME = "Asia/Jerusalem"
SOURCE_TIMEZONE = ZoneInfo(TIMEZONE_NAME)
MONTH_FILES = [
    "January1999.txt",
    "February1999.txt",
    "March1999.txt",
    "April1999.txt",
    "May1999.txt",
    "June1999.txt",
    "July1999.txt",
    "August1999.txt",
    "September1999.txt",
    "October1999.txt",
    "November1999.txt",
    "December1999.txt",
]
SOURCE_COLUMNS = [
    "vru_line",
    "call_id",
    "customer_id",
    "priority",
    "service_type",
    "date",
    "vru_entry",
    "vru_exit",
    "vru_time",
    "q_start",
    "q_exit",
    "q_time",
    "outcome",
    "ser_start",
    "ser_exit",
    "ser_time",
    "server",
]
RAW_HEADER = [
    "vru+line",
    "call_id",
    "customer_id",
    "priority",
    "type",
    "date",
    "vru_entry",
    "vru_exit",
    "vru_time",
    "q_start",
    "q_exit",
    "q_time",
    "outcome",
    "ser_start",
    "ser_exit",
    "ser_time",
    "server",
]
SERVICE_TYPE_LABELS = {
    "PS": "regular_activity",
    "PE": "regular_activity_english",
    "IN": "internet_consulting",
    "NE": "stock_exchange_activity",
    "NW": "prospective_customer_information",
    "TT": "callback_related_queue_call",
}
VALID_PRIORITIES = {"0", "1", "2"}
VALID_OUTCOMES = {"AGENT", "HANG", "PHANTOM"}
MALFORMED_PRIORITY_TYPE = re.compile(r"^\s*([012])\s+(PS|PE|IN|NE|NW|TT)\s*$")

CLEAN_COLUMNS = [
    "source_call_key",
    "source_file",
    "source_line_number",
    "vru_line",
    "call_id",
    "priority",
    "service_type_code",
    "service_type_label",
    "source_timezone",
    "offered_at",
    "vru_exited_at",
    "queue_started_at",
    "queue_exited_at",
    "answered_at",
    "abandoned_at",
    "service_ended_at",
    "call_status",
    "reached_queue",
    "vru_seconds_source",
    "vru_seconds_recomputed",
    "vru_seconds",
    "wait_seconds_source",
    "wait_seconds_recomputed",
    "wait_seconds",
    "service_seconds_source",
    "service_seconds_recomputed",
    "service_seconds",
    "interval_start",
    "date_key",
    "interval_key",
    "agent_id",
    "agent_identified",
    "answered_in_threshold",
    "is_short_abandon",
    "valid_for_aht",
    "data_origin",
    "repair_codes",
    "quality_flags",
]
EXCLUDED_COLUMNS = [
    "source_call_key",
    "source_file",
    "source_line_number",
    "vru_line",
    "call_id",
    "priority",
    "service_type_code",
    "outcome",
    "exclusion_reason",
    "repair_codes",
    "data_origin",
]
QUARANTINE_COLUMNS = [
    "source_file",
    "source_line_number",
    "source_call_key",
    "vru_line",
    "call_id",
    "priority",
    "service_type_code",
    "outcome",
    "observed_field_count",
    "quarantine_reason",
    "data_origin",
]
INTERVAL_COLUMNS = [
    "interval_start",
    "source_timezone",
    "date_key",
    "interval_key",
    "offered_calls",
    "answered_calls",
    "abandoned_calls",
    "short_abandon_calls",
    "answered_within_20s",
    "service_level_denominator",
    "service_level_rate",
    "total_wait_seconds",
    "avg_wait_seconds",
    "aht_eligible_calls",
    "total_service_seconds_for_aht",
    "aht_proxy_seconds",
    "data_origin",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_paths() -> list[Path]:
    paths = [RAW_DIR / name for name in MONTH_FILES]
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing source files: {', '.join(missing)}")
    return paths


def parse_source_parts(line: str) -> tuple[list[str] | None, list[str], int]:
    """Return parsed fields, repair codes, and the original field count."""
    parts = [value.strip() for value in line.rstrip("\r\n").split("\t")]
    original_count = len(parts)
    repairs: list[str] = []
    if len(parts) == 16:
        match = MALFORMED_PRIORITY_TYPE.fullmatch(parts[3])
        if match:
            parts = parts[:3] + [match.group(1), match.group(2)] + parts[4:]
            repairs.append("split_merged_priority_service_type")
    if len(parts) != len(SOURCE_COLUMNS):
        return None, repairs, original_count
    return parts, repairs, original_count


def iter_parsed_rows() -> Iterable[tuple[Path, int, dict[str, str], list[str], int]]:
    for path in source_paths():
        with path.open(encoding="ascii", newline="") as source_file:
            header = source_file.readline().rstrip("\r\n").split("\t")
            if header != RAW_HEADER:
                raise ValueError(f"Unexpected header in {path.name}: {header}")
            for line_number, line in enumerate(source_file, start=2):
                parts, repairs, original_count = parse_source_parts(line)
                if parts is None:
                    yield path, line_number, {}, repairs, original_count
                    continue
                yield (
                    path,
                    line_number,
                    dict(zip(SOURCE_COLUMNS, parts, strict=True)),
                    repairs,
                    original_count,
                )


def agent_mapping() -> dict[str, str]:
    labels: set[str] = set()
    for _, _, row, _, _ in iter_parsed_rows():
        if not row:
            continue
        label = row["server"]
        if row["outcome"] == "AGENT" and label and label != "NO_SERVER":
            labels.add(label)
    return {label: f"AGENT_{index:03d}" for index, label in enumerate(sorted(labels), start=1)}


def source_call_key(path: Path, row: dict[str, str]) -> str:
    return f"{path.stem}|{row.get('vru_line', '')}|{row.get('call_id', '')}"


def integer(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_source_date(value: str) -> date | None:
    try:
        return datetime.strptime(f"19{value.zfill(6)}", "%Y%m%d").date()
    except ValueError:
        return None


def parse_clock(value: str) -> time | None:
    try:
        return datetime.strptime(value, "%H:%M:%S").time()
    except ValueError:
        return None


def combine_local(day: date, clock_text: str) -> datetime | None:
    clock = parse_clock(clock_text)
    if clock is None:
        return None
    return datetime.combine(day, clock, tzinfo=SOURCE_TIMEZONE)


def relative_event(
    day: date,
    clock_text: str,
    previous: datetime,
    maximum_elapsed_seconds: int,
    backward_tolerance_seconds: int = 5,
) -> tuple[datetime | None, str | None]:
    candidate = combine_local(day, clock_text)
    if candidate is None:
        return None, "invalid_time"
    if candidate < previous:
        # Source clocks occasionally differ by one or two seconds at a stage
        # boundary. Preserve the observed timestamp and make the skew explicit
        # instead of incorrectly treating it as a next-day event.
        if (previous - candidate).total_seconds() <= backward_tolerance_seconds:
            return candidate, "minor_clock_skew"
        rollover = candidate + timedelta(days=1)
        if 0 <= (rollover - previous).total_seconds() <= maximum_elapsed_seconds:
            return rollover, "midnight_rollover"
        return None, "invalid_time_sequence"
    if (candidate - previous).total_seconds() > maximum_elapsed_seconds:
        return None, "implausible_elapsed_time"
    return candidate, None


def recomputed_seconds(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    seconds = int((end - start).total_seconds())
    return seconds if seconds >= 0 else None


def iso(value: datetime | None) -> str:
    return "" if value is None else value.isoformat()


def boolean(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def value_or_blank(value: Any) -> Any:
    return "" if value is None else value


def basic_quarantine_row(
    path: Path,
    line_number: int,
    row: dict[str, str],
    original_count: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "source_file": path.name,
        "source_line_number": line_number,
        "source_call_key": source_call_key(path, row) if row else "",
        "vru_line": row.get("vru_line", ""),
        "call_id": row.get("call_id", ""),
        "priority": row.get("priority", ""),
        "service_type_code": row.get("service_type", ""),
        "outcome": row.get("outcome", ""),
        "observed_field_count": original_count,
        "quarantine_reason": reason,
        "data_origin": "source_observed",
    }


def transform_row(
    path: Path,
    line_number: int,
    row: dict[str, str],
    repairs: list[str],
    agents: dict[str, str],
) -> tuple[str, dict[str, Any], list[str]]:
    quality_flags: list[str] = []
    key = source_call_key(path, row)

    if row["priority"] not in VALID_PRIORITIES:
        return "quarantine", basic_quarantine_row(
            path, line_number, row, len(SOURCE_COLUMNS), "unexpected_priority"
        ), quality_flags
    if row["service_type"] not in SERVICE_TYPE_LABELS:
        return "quarantine", basic_quarantine_row(
            path, line_number, row, len(SOURCE_COLUMNS), "unexpected_service_type"
        ), quality_flags
    if row["outcome"] not in VALID_OUTCOMES:
        return "quarantine", basic_quarantine_row(
            path, line_number, row, len(SOURCE_COLUMNS), "unexpected_outcome"
        ), quality_flags

    if row["outcome"] == "PHANTOM":
        return (
            "excluded",
            {
                "source_call_key": key,
                "source_file": path.name,
                "source_line_number": line_number,
                "vru_line": row["vru_line"],
                "call_id": row["call_id"],
                "priority": row["priority"],
                "service_type_code": row["service_type"],
                "outcome": row["outcome"],
                "exclusion_reason": "phantom_record",
                "repair_codes": ";".join(repairs),
                "data_origin": "source_observed",
            },
            quality_flags,
        )

    source_date = parse_source_date(row["date"])
    if source_date is None:
        return "quarantine", basic_quarantine_row(
            path, line_number, row, len(SOURCE_COLUMNS), "invalid_date"
        ), quality_flags
    offered_at = combine_local(source_date, row["vru_entry"])
    if offered_at is None:
        return "quarantine", basic_quarantine_row(
            path, line_number, row, len(SOURCE_COLUMNS), "invalid_vru_entry"
        ), quality_flags

    vru_source = integer(row["vru_time"])
    queue_source = integer(row["q_time"])
    service_source = integer(row["ser_time"])
    if queue_source is None or queue_source < 0:
        return "quarantine", basic_quarantine_row(
            path, line_number, row, len(SOURCE_COLUMNS), "invalid_queue_duration"
        ), quality_flags
    if service_source is None or service_source < 0:
        return "quarantine", basic_quarantine_row(
            path, line_number, row, len(SOURCE_COLUMNS), "invalid_service_duration"
        ), quality_flags

    vru_exited_at, vru_time_flag = relative_event(
        source_date, row["vru_exit"], offered_at, 3_600
    )
    if vru_time_flag:
        quality_flags.append(f"vru_exit_{vru_time_flag}")
    vru_recomputed = recomputed_seconds(offered_at, vru_exited_at)
    if vru_source is None:
        quality_flags.append("invalid_vru_duration")
        vru_seconds = vru_recomputed
    elif vru_source < 0:
        quality_flags.append("negative_vru_duration")
        vru_seconds = vru_recomputed
    else:
        vru_seconds = vru_source

    no_queue = (
        queue_source == 0
        and parse_clock(row["q_start"]) == time(0, 0)
        and parse_clock(row["q_exit"]) == time(0, 0)
    )
    queue_started_at: datetime | None = None
    queue_exited_at: datetime | None = None
    if not no_queue:
        queue_started_at, flag = relative_event(
            source_date, row["q_start"], offered_at, 86_400
        )
        if flag:
            quality_flags.append(f"queue_start_{flag}")
        if queue_started_at is not None:
            queue_exited_at, flag = relative_event(
                source_date, row["q_exit"], queue_started_at, 43_200
            )
            if flag:
                quality_flags.append(f"queue_exit_{flag}")
    queue_recomputed = recomputed_seconds(queue_started_at, queue_exited_at)

    no_service = (
        service_source == 0
        and parse_clock(row["ser_start"]) == time(0, 0)
        and parse_clock(row["ser_exit"]) == time(0, 0)
    )
    service_started_at: datetime | None = None
    service_ended_at: datetime | None = None
    if not no_service:
        service_reference = queue_exited_at or vru_exited_at or offered_at
        service_started_at, flag = relative_event(
            source_date, row["ser_start"], service_reference, 86_400
        )
        if flag:
            quality_flags.append(f"service_start_{flag}")
        if service_started_at is not None:
            service_ended_at, flag = relative_event(
                source_date, row["ser_exit"], service_started_at, 43_200
            )
            if flag:
                quality_flags.append(f"service_end_{flag}")
    service_recomputed = recomputed_seconds(service_started_at, service_ended_at)

    call_status = "answered" if row["outcome"] == "AGENT" else "abandoned"
    raw_agent_label = row["server"]
    has_agent_label = raw_agent_label not in {"", "NO_SERVER"}
    agent_id = agents.get(raw_agent_label, "") if call_status == "answered" else ""
    if call_status == "answered" and not has_agent_label:
        quality_flags.append("answered_without_agent_label")
    if call_status == "abandoned" and has_agent_label:
        quality_flags.append("abandoned_with_agent_label")
    if call_status == "answered" and service_source == 0:
        quality_flags.append("zero_service_duration")

    answered_at = service_started_at if call_status == "answered" else None
    abandoned_at = (
        (queue_exited_at or vru_exited_at) if call_status == "abandoned" else None
    )
    interval_minute = 0 if offered_at.minute < 30 else 30
    interval_start = offered_at.replace(minute=interval_minute, second=0, microsecond=0)
    valid_for_aht = (
        call_status == "answered"
        and bool(agent_id)
        and service_source > 0
        and service_started_at is not None
        and service_ended_at is not None
    )

    clean = {
        "source_call_key": key,
        "source_file": path.name,
        "source_line_number": line_number,
        "vru_line": row["vru_line"],
        "call_id": row["call_id"],
        "priority": int(row["priority"]),
        "service_type_code": row["service_type"],
        "service_type_label": SERVICE_TYPE_LABELS[row["service_type"]],
        "source_timezone": TIMEZONE_NAME,
        "offered_at": iso(offered_at),
        "vru_exited_at": iso(vru_exited_at),
        "queue_started_at": iso(queue_started_at),
        "queue_exited_at": iso(queue_exited_at),
        "answered_at": iso(answered_at),
        "abandoned_at": iso(abandoned_at),
        "service_ended_at": iso(service_ended_at),
        "call_status": call_status,
        "reached_queue": boolean(queue_started_at is not None),
        "vru_seconds_source": value_or_blank(vru_source),
        "vru_seconds_recomputed": value_or_blank(vru_recomputed),
        "vru_seconds": value_or_blank(vru_seconds),
        "wait_seconds_source": queue_source,
        "wait_seconds_recomputed": value_or_blank(queue_recomputed),
        "wait_seconds": queue_source,
        "service_seconds_source": service_source,
        "service_seconds_recomputed": value_or_blank(service_recomputed),
        "service_seconds": service_source,
        "interval_start": iso(interval_start),
        "date_key": offered_at.strftime("%Y%m%d"),
        "interval_key": offered_at.replace(
            minute=interval_minute, second=0, microsecond=0
        ).strftime("%H%M"),
        "agent_id": agent_id,
        "agent_identified": boolean(bool(agent_id)),
        "answered_in_threshold": boolean(
            call_status == "answered" and queue_source <= 20
        ),
        "is_short_abandon": boolean(
            call_status == "abandoned" and queue_source <= 5
        ),
        "valid_for_aht": boolean(valid_for_aht),
        "data_origin": "source_observed_and_derived",
        "repair_codes": ";".join(repairs),
        "quality_flags": ";".join(sorted(set(quality_flags))),
    }
    return "clean", clean, quality_flags


def observe_source_issues(row: dict[str, str], issues: Counter[str]) -> None:
    """Count known source issues before records are routed to an output stream."""
    vru_seconds = integer(row["vru_time"])
    service_seconds = integer(row["ser_time"])
    has_agent_label = row["server"] not in {"", "NO_SERVER"}
    if vru_seconds is not None and vru_seconds < 0:
        issues["negative_vru_duration"] += 1
    if row["service_type"] not in SERVICE_TYPE_LABELS:
        issues["unexpected_service_type"] += 1
    if row["outcome"] == "AGENT" and not has_agent_label:
        issues["answered_without_agent_label"] += 1
    if row["outcome"] == "HANG" and has_agent_label:
        issues["abandoned_with_agent_label"] += 1
    if row["outcome"] == "AGENT" and service_seconds == 0:
        issues["answered_with_zero_service_duration"] += 1


def update_interval_metrics(
    metrics: dict[str, Counter[str]], clean: dict[str, Any]
) -> None:
    bucket = metrics.setdefault(clean["interval_start"], Counter())
    bucket["offered_calls"] += 1
    bucket[f"{clean['call_status']}_calls"] += 1
    bucket["total_wait_seconds"] += int(clean["wait_seconds"])
    if clean["is_short_abandon"] == "true":
        bucket["short_abandon_calls"] += 1
    if clean["answered_in_threshold"] == "true":
        bucket["answered_within_20s"] += 1
    if clean["valid_for_aht"] == "true":
        bucket["aht_eligible_calls"] += 1
        bucket["total_service_seconds_for_aht"] += int(clean["service_seconds"])


def write_interval_output(
    path: Path, metrics: dict[str, Counter[str]]
) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as interval_file:
        writer = csv.DictWriter(interval_file, fieldnames=INTERVAL_COLUMNS)
        writer.writeheader()
        for interval_start in sorted(metrics):
            bucket = metrics[interval_start]
            offered = bucket["offered_calls"]
            short_abandons = bucket["short_abandon_calls"]
            sl_denominator = offered - short_abandons
            aht_count = bucket["aht_eligible_calls"]
            parsed_start = datetime.fromisoformat(interval_start)
            writer.writerow(
                {
                    "interval_start": interval_start,
                    "source_timezone": TIMEZONE_NAME,
                    "date_key": parsed_start.strftime("%Y%m%d"),
                    "interval_key": parsed_start.strftime("%H%M"),
                    "offered_calls": offered,
                    "answered_calls": bucket["answered_calls"],
                    "abandoned_calls": bucket["abandoned_calls"],
                    "short_abandon_calls": short_abandons,
                    "answered_within_20s": bucket["answered_within_20s"],
                    "service_level_denominator": sl_denominator,
                    "service_level_rate": (
                        round(bucket["answered_within_20s"] / sl_denominator, 6)
                        if sl_denominator
                        else ""
                    ),
                    "total_wait_seconds": bucket["total_wait_seconds"],
                    "avg_wait_seconds": round(
                        bucket["total_wait_seconds"] / offered, 3
                    ),
                    "aht_eligible_calls": aht_count,
                    "total_service_seconds_for_aht": bucket[
                        "total_service_seconds_for_aht"
                    ],
                    "aht_proxy_seconds": (
                        round(bucket["total_service_seconds_for_aht"] / aht_count, 3)
                        if aht_count
                        else ""
                    ),
                    "data_origin": "source_observed_aggregated_and_derived",
                }
            )


def write_reports(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / "etl_reconciliation.json"
    markdown_path = REPORT_DIR / "etl_reconciliation.md"
    checksum_path = REPORT_DIR / "etl_reconciliation.sha256"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summary = report["summary"]
    lines = [
        "# ETL Reconciliation Report",
        "",
        f"Generated at UTC: `{report['generated_at_utc']}`",
        "",
        "## Row reconciliation",
        "",
        f"- Raw rows: **{summary['raw_rows']:,}**",
        f"- Clean rows: **{summary['clean_rows']:,}**",
        f"- Excluded rows: **{summary['excluded_rows']:,}**",
        f"- Quarantine rows: **{summary['quarantine_rows']:,}**",
        f"- Repaired rows: **{summary['repaired_rows']:,}**",
        f"- 30-minute interval rows: **{summary['interval_rows']:,}**",
        f"- Offered calls across intervals: **{summary['interval_offered_calls']:,}**",
        f"- Reconciliation passed: **{summary['reconciliation_passed']}**",
        "",
        "```text",
        f"{summary['raw_rows']:,} = {summary['clean_rows']:,} + "
        f"{summary['excluded_rows']:,} + {summary['quarantine_rows']:,}",
        "```",
        "",
        "## Reasons and quality flags",
        "",
        f"- Exclusion reasons: `{json.dumps(report['exclusion_reasons'], sort_keys=True)}`",
        f"- Quarantine reasons: `{json.dumps(report['quarantine_reasons'], sort_keys=True)}`",
        f"- Repair codes: `{json.dumps(report['repair_codes'], sort_keys=True)}`",
        f"- Quality flags: `{json.dumps(report['quality_flags'], sort_keys=True)}`",
        f"- Source issues observed: `{json.dumps(report['source_issue_counts'], sort_keys=True)}`",
        "",
        "Customer IDs and raw agent labels are not present in any ETL output.",
        "",
    ]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    checksum_path.write_text(
        f"{sha256(json_path)}  {json_path.name}\n"
        f"{sha256(markdown_path)}  {markdown_path.name}\n",
        encoding="ascii",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_path = OUTPUT_DIR / "calls_clean.csv.gz"
    excluded_path = OUTPUT_DIR / "calls_excluded.csv.gz"
    quarantine_path = OUTPUT_DIR / "calls_quarantine.csv.gz"
    interval_path = OUTPUT_DIR / "calls_interval_30m.csv.gz"
    agents = agent_mapping()

    stream_counts: Counter[str] = Counter()
    exclusion_reasons: Counter[str] = Counter()
    quarantine_reasons: Counter[str] = Counter()
    repair_codes: Counter[str] = Counter()
    quality_flags: Counter[str] = Counter()
    source_issue_counts: Counter[str] = Counter()
    interval_metrics: dict[str, Counter[str]] = {}

    with (
        gzip.open(clean_path, "wt", encoding="utf-8", newline="") as clean_file,
        gzip.open(excluded_path, "wt", encoding="utf-8", newline="") as excluded_file,
        gzip.open(quarantine_path, "wt", encoding="utf-8", newline="") as quarantine_file,
    ):
        clean_writer = csv.DictWriter(clean_file, fieldnames=CLEAN_COLUMNS)
        excluded_writer = csv.DictWriter(excluded_file, fieldnames=EXCLUDED_COLUMNS)
        quarantine_writer = csv.DictWriter(quarantine_file, fieldnames=QUARANTINE_COLUMNS)
        clean_writer.writeheader()
        excluded_writer.writeheader()
        quarantine_writer.writeheader()

        for path, line_number, row, repairs, original_count in iter_parsed_rows():
            for repair in repairs:
                repair_codes[repair] += 1
            if not row:
                result = basic_quarantine_row(
                    path,
                    line_number,
                    row,
                    original_count,
                    "malformed_delimiter_unrepairable",
                )
                quarantine_writer.writerow(result)
                stream_counts["quarantine"] += 1
                quarantine_reasons[result["quarantine_reason"]] += 1
                continue

            observe_source_issues(row, source_issue_counts)

            stream, transformed, row_flags = transform_row(
                path, line_number, row, repairs, agents
            )
            stream_counts[stream] += 1
            quality_flags.update(row_flags)
            if stream == "clean":
                clean_writer.writerow(transformed)
                update_interval_metrics(interval_metrics, transformed)
            elif stream == "excluded":
                excluded_writer.writerow(transformed)
                exclusion_reasons[transformed["exclusion_reason"]] += 1
            else:
                quarantine_writer.writerow(transformed)
                quarantine_reasons[transformed["quarantine_reason"]] += 1

    write_interval_output(interval_path, interval_metrics)

    raw_rows = sum(stream_counts.values())
    expected_raw_rows = 444_448
    if raw_rows != expected_raw_rows:
        raise RuntimeError(f"Raw row count changed: expected {expected_raw_rows}, got {raw_rows}")
    reconciled = raw_rows == (
        stream_counts["clean"]
        + stream_counts["excluded"]
        + stream_counts["quarantine"]
    )
    if not reconciled:
        raise RuntimeError("ETL reconciliation failed")
    interval_offered_calls = sum(
        bucket["offered_calls"] for bucket in interval_metrics.values()
    )
    if interval_offered_calls != stream_counts["clean"]:
        raise RuntimeError(
            "30-minute aggregation failed: "
            f"expected {stream_counts['clean']} offered calls, "
            f"got {interval_offered_calls}"
        )

    report = {
        "report_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_timezone_assumption": TIMEZONE_NAME,
        "summary": {
            "raw_rows": raw_rows,
            "clean_rows": stream_counts["clean"],
            "excluded_rows": stream_counts["excluded"],
            "quarantine_rows": stream_counts["quarantine"],
            "repaired_rows": sum(repair_codes.values()),
            "interval_rows": len(interval_metrics),
            "interval_offered_calls": interval_offered_calls,
            "reconciliation_passed": reconciled,
        },
        "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        "quarantine_reasons": dict(sorted(quarantine_reasons.items())),
        "repair_codes": dict(sorted(repair_codes.items())),
        "quality_flags": dict(sorted(quality_flags.items())),
        "source_issue_counts": dict(sorted(source_issue_counts.items())),
        "agent_pseudonymization": {
            "method": "deterministic sequential IDs from sorted source labels",
            "agent_count": len(agents),
            "raw_agent_labels_written_to_output": False,
        },
        "privacy": {
            "customer_id_written_to_output": False,
            "raw_agent_label_written_to_output": False,
        },
        "outputs": {
            path.name: {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in (clean_path, excluded_path, quarantine_path, interval_path)
        },
    }
    write_reports(report)
    print(
        f"Reconciled {raw_rows:,} rows: clean={stream_counts['clean']:,}, "
        f"excluded={stream_counts['excluded']:,}, "
        f"quarantine={stream_counts['quarantine']:,}"
    )
    print(f"Repaired rows: {sum(repair_codes.values()):,}")
    print(
        f"30-minute intervals: {len(interval_metrics):,}; "
        f"offered calls={interval_offered_calls:,}"
    )
    print(f"Outputs: {OUTPUT_DIR.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
