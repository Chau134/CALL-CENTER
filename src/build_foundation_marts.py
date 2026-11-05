"""Build forecast-ready calendar, interval, queue, and service-type marts.

The source documentation states that the archive contains all calls for the
full 1999 calendar year and that the VRU ran 24/7. Zero-filled intervals are
therefore created only after the raw baseline and all monthly files reconcile.
No workforce or customer data is synthesized by this module.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

try:
    from .transform_calls import (
        MONTH_FILES,
        PROJECT_ROOT,
        RAW_DIR,
        SERVICE_TYPE_LABELS,
        SOURCE_TIMEZONE,
        TIMEZONE_NAME,
        VALID_OUTCOMES,
        VALID_PRIORITIES,
        integer,
        iter_parsed_rows,
        parse_clock,
        parse_source_date,
        sha256,
    )
except ImportError:  # Support direct execution: python src/build_foundation_marts.py
    from transform_calls import (
        MONTH_FILES,
        PROJECT_ROOT,
        RAW_DIR,
        SERVICE_TYPE_LABELS,
        SOURCE_TIMEZONE,
        TIMEZONE_NAME,
        VALID_OUTCOMES,
        VALID_PRIORITIES,
        integer,
        iter_parsed_rows,
        parse_clock,
        parse_source_date,
        sha256,
    )


INPUT_DIR = PROJECT_ROOT / "data" / "interim" / "technion"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "technion"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"
CONFIG_PATH = PROJECT_ROOT / "config" / "project.yml"
BASELINE_PATH = REPORT_DIR / "raw_baseline.json"
HOLIDAY_PATH = REFERENCE_DIR / "israel_holidays_1999.csv"
SOURCE_REFERENCE = (
    "https://see-center.iem.technion.ac.il/databases/AnonymousBank/"
    "Data/AnonymousBank.pdf"
)
HOLIDAY_REFERENCE = "https://www.hebcal.com/holidays/1999?i=on"
QUEUE_ID = "INBOUND_SUPPORT"
CHANNEL = "inbound_voice"
DIRECTION = "inbound"
START_DATE = date(1999, 1, 1)
END_DATE = date(1999, 12, 31)
GENERATION_METHOD = "build_foundation_marts.py"
GENERATION_VERSION = "1.0.0"


QUEUE_COLUMNS = [
    "date_key",
    "interval_key",
    "queue_id",
    "local_interval_start",
    "local_interval_end",
    "interval_start_assumed",
    "interval_end_assumed",
    "interval_start_utc",
    "interval_end_utc",
    "actual_interval_seconds",
    "source_timezone",
    "interval_minutes",
    "channel",
    "direction",
    "raw_record_count",
    "excluded_record_count",
    "quarantine_record_count",
    "has_source_records",
    "has_calls",
    "source_file_available",
    "source_date_covered",
    "interval_coverage_verified",
    "source_period_covered",
    "is_operating_interval",
    "is_closed_interval",
    "coverage_status",
    "zero_fill_reason",
    "dst_transition_flag",
    "dst_status",
    "offered_calls",
    "agent_demand_calls",
    "answered_calls",
    "abandoned_calls",
    "queue_abandoned_calls",
    "vru_abandoned_calls",
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
    "source_reference",
    "generation_method",
    "generation_version",
    "etl_run_id",
]

SERVICE_INTERVAL_COLUMNS = [
    "date_key",
    "interval_key",
    "service_type_code",
    "service_type_name",
    "queue_id",
    "local_interval_start",
    "source_timezone",
    "coverage_status",
    "is_operating_interval",
    "offered_calls",
    "agent_demand_calls",
    "answered_calls",
    "abandoned_calls",
    "queue_abandoned_calls",
    "vru_abandoned_calls",
    "short_abandon_calls",
    "answered_within_20s",
    "valid_for_aht_calls",
    "wait_seconds_sum",
    "service_seconds_sum_for_aht",
    "aht_proxy_seconds",
    "data_origin",
    "source_reference",
    "generation_method",
    "generation_version",
    "etl_run_id",
]


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def date_range(start: date, end: date) -> Iterator[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def minute_of_day(value: str) -> int:
    hour_text, minute_text = value.split(":", maxsplit=1)
    hour = int(hour_text)
    minute = int(minute_text)
    if hour == 24 and minute == 0:
        return 24 * 60
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid wall-clock time: {value}")
    return hour * 60 + minute


def interval_key_for(clock: time) -> str:
    minute = 0 if clock.minute < 30 else 30
    return f"{clock.hour:02d}{minute:02d}"


def day_name_key(day: date) -> str:
    return day.strftime("%A").lower()


def is_operating_interval(
    day: date, interval_key: str, staffed_hours: dict[str, list[str]]
) -> bool:
    start_text, end_text = staffed_hours[day_name_key(day)]
    interval_minutes = int(interval_key[:2]) * 60 + int(interval_key[2:])
    return minute_of_day(start_text) <= interval_minutes < minute_of_day(end_text)


def daypart_for(interval_key: str, dayparts: dict[str, list[str]]) -> str:
    interval_minutes = int(interval_key[:2]) * 60 + int(interval_key[2:])
    matches = [
        name
        for name, (start_text, end_text) in dayparts.items()
        if minute_of_day(start_text) <= interval_minutes < minute_of_day(end_text)
    ]
    if len(matches) != 1:
        raise ValueError(f"Interval {interval_key} maps to dayparts {matches}")
    return matches[0]


def wall_time_candidates(local_value: datetime) -> list[datetime]:
    candidates: list[datetime] = []
    seen_utc: set[datetime] = set()
    for fold in (0, 1):
        aware = local_value.replace(tzinfo=SOURCE_TIMEZONE, fold=fold)
        utc_value = aware.astimezone(timezone.utc)
        round_trip = utc_value.astimezone(SOURCE_TIMEZONE).replace(tzinfo=None)
        if round_trip == local_value and utc_value not in seen_utc:
            candidates.append(aware)
            seen_utc.add(utc_value)
    return candidates


def wall_time_metadata(local_value: datetime) -> dict[str, Any]:
    candidates = wall_time_candidates(local_value)
    if not candidates:
        return {
            "status": "nonexistent",
            "assumed": "",
            "utc": "",
            "candidate_count": 0,
        }
    if len(candidates) > 1:
        return {
            "status": "ambiguous",
            "assumed": candidates[0].isoformat(),
            "utc": "",
            "candidate_count": len(candidates),
        }
    return {
        "status": "normal",
        "assumed": candidates[0].isoformat(),
        "utc": candidates[0].astimezone(timezone.utc).isoformat(),
        "candidate_count": 1,
    }


def interval_time_metadata(day: date, interval_key: str) -> dict[str, Any]:
    hour = int(interval_key[:2])
    minute = int(interval_key[2:])
    local_start = datetime.combine(day, time(hour, minute))
    local_end = local_start + timedelta(minutes=30)
    start_meta = wall_time_metadata(local_start)
    end_meta = wall_time_metadata(local_end)
    transition = start_meta["status"] != "normal" or end_meta["status"] != "normal"
    actual_seconds: int | str = ""
    if start_meta["utc"] and end_meta["utc"]:
        actual_seconds = int(
            (
                datetime.fromisoformat(end_meta["utc"])
                - datetime.fromisoformat(start_meta["utc"])
            ).total_seconds()
        )
        if actual_seconds != 1800:
            transition = True
    status = start_meta["status"]
    if status == "normal" and end_meta["status"] != "normal":
        status = f"ends_{end_meta['status']}"
    return {
        "local_start": local_start.isoformat(),
        "local_end": local_end.isoformat(),
        "start_assumed": start_meta["assumed"],
        "end_assumed": end_meta["assumed"],
        "start_utc": start_meta["utc"],
        "end_utc": end_meta["utc"],
        "actual_seconds": actual_seconds,
        "dst_transition": transition,
        "dst_status": status,
    }


def load_holidays() -> dict[date, list[dict[str, str]]]:
    holidays: dict[date, list[dict[str, str]]] = defaultdict(list)
    with HOLIDAY_PATH.open(encoding="utf-8", newline="") as holiday_file:
        for row in csv.DictReader(holiday_file):
            calendar_date = date.fromisoformat(row["calendar_date"])
            if not START_DATE <= calendar_date <= END_DATE:
                raise ValueError(f"Holiday outside source year: {calendar_date}")
            holidays[calendar_date].append(row)
    return holidays


def load_raw_baseline() -> dict[str, Any]:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    files = {item["file_name"]: item for item in baseline["files"]}
    if set(files) != set(MONTH_FILES):
        raise RuntimeError("Raw baseline does not contain the expected 12 monthly files")
    for filename, metadata in files.items():
        path = RAW_DIR / filename
        if not path.exists():
            raise RuntimeError(f"Missing raw source file: {filename}")
        if path.stat().st_size != metadata["size_bytes"] or sha256(path) != metadata["sha256"]:
            raise RuntimeError(f"Raw source integrity changed: {filename}")
    return baseline


def load_queue_metrics() -> dict[tuple[str, str], dict[str, str]]:
    path = INPUT_DIR / "calls_interval_30m.csv.gz"
    metrics: dict[tuple[str, str], dict[str, str]] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file):
            key = (row["date_key"], row["interval_key"])
            if key in metrics:
                raise RuntimeError(f"Duplicate source interval: {key}")
            metrics[key] = row
    return metrics


def load_call_metrics() -> tuple[
    dict[tuple[str, str, str], Counter[str]],
    dict[tuple[str, str], Counter[str]],
]:
    path = INPUT_DIR / "calls_clean.csv.gz"
    metrics: dict[tuple[str, str, str], Counter[str]] = {}
    demand_metrics: dict[tuple[str, str], Counter[str]] = {}
    with gzip.open(path, "rt", encoding="utf-8", newline="") as input_file:
        for row in csv.DictReader(input_file):
            key = (row["date_key"], row["interval_key"], row["service_type_code"])
            bucket = metrics.setdefault(key, Counter())
            demand_bucket = demand_metrics.setdefault(
                (row["date_key"], row["interval_key"]), Counter()
            )
            bucket["offered_calls"] += 1
            bucket[f"{row['call_status']}_calls"] += 1
            bucket["wait_seconds_sum"] += int(row["wait_seconds"])
            if row["is_short_abandon"] == "true":
                bucket["short_abandon_calls"] += 1
            if row["answered_in_threshold"] == "true":
                bucket["answered_within_20s"] += 1
            if row["valid_for_aht"] == "true":
                bucket["valid_for_aht_calls"] += 1
                bucket["service_seconds_sum_for_aht"] += int(row["service_seconds"])
            reached_queue = row["reached_queue"] == "true"
            is_answered = row["call_status"] == "answered"
            is_queue_abandon = row["call_status"] == "abandoned" and reached_queue
            is_vru_abandon = row["call_status"] == "abandoned" and not reached_queue
            if is_answered or is_queue_abandon:
                bucket["agent_demand_calls"] += 1
                demand_bucket["agent_demand_calls"] += 1
            if is_queue_abandon:
                bucket["queue_abandoned_calls"] += 1
                demand_bucket["queue_abandoned_calls"] += 1
            if is_vru_abandon:
                bucket["vru_abandoned_calls"] += 1
                demand_bucket["vru_abandoned_calls"] += 1
    return metrics, demand_metrics


def raw_interval_counts() -> dict[tuple[str, str], Counter[str]]:
    counts: dict[tuple[str, str], Counter[str]] = {}
    unassigned = 0
    for _, _, row, _, _ in iter_parsed_rows():
        if not row:
            unassigned += 1
            continue
        source_date = parse_source_date(row["date"])
        source_clock = parse_clock(row["vru_entry"])
        if source_date is None or source_clock is None:
            unassigned += 1
            continue
        key = (source_date.strftime("%Y%m%d"), interval_key_for(source_clock))
        bucket = counts.setdefault(key, Counter())
        bucket["raw_record_count"] += 1
        if (
            row["priority"] not in VALID_PRIORITIES
            or row["service_type"] not in SERVICE_TYPE_LABELS
            or row["outcome"] not in VALID_OUTCOMES
            or integer(row["q_time"]) is None
            or integer(row["q_time"]) < 0
            or integer(row["ser_time"]) is None
            or integer(row["ser_time"]) < 0
        ):
            bucket["quarantine_record_count"] += 1
        elif row["outcome"] == "PHANTOM":
            bucket["excluded_record_count"] += 1
        else:
            bucket["clean_record_count"] += 1
    if unassigned:
        raise RuntimeError(f"Raw rows could not be assigned to an interval: {unassigned}")
    return counts


def csv_gzip_writer(path: Path, columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    output_file = gzip.open(path, "wt", encoding="utf-8", newline="")
    writer = csv.DictWriter(output_file, fieldnames=columns, extrasaction="raise")
    writer.writeheader()
    return output_file, writer


def common_audit(data_origin: str, etl_run_id: str) -> dict[str, str]:
    return {
        "data_origin": data_origin,
        "source_reference": SOURCE_REFERENCE,
        "generation_method": GENERATION_METHOD,
        "generation_version": GENERATION_VERSION,
        "etl_run_id": etl_run_id,
    }


def build_dim_time_interval(
    path: Path, dayparts: dict[str, list[str]], etl_run_id: str
) -> None:
    columns = [
        "interval_key",
        "interval_number",
        "start_time",
        "end_time",
        "interval_minutes",
        "hour_number",
        "minute_number",
        "daypart",
        "data_origin",
        "generation_method",
        "generation_version",
        "etl_run_id",
    ]
    output_file, writer = csv_gzip_writer(path, columns)
    with output_file:
        for interval_number in range(48):
            total_minutes = interval_number * 30
            hour, minute = divmod(total_minutes, 60)
            end_minutes = (total_minutes + 30) % (24 * 60)
            end_hour, end_minute = divmod(end_minutes, 60)
            key = f"{hour:02d}{minute:02d}"
            writer.writerow(
                {
                    "interval_key": key,
                    "interval_number": interval_number,
                    "start_time": f"{hour:02d}:{minute:02d}:00",
                    "end_time": f"{end_hour:02d}:{end_minute:02d}:00",
                    "interval_minutes": 30,
                    "hour_number": hour,
                    "minute_number": minute,
                    "daypart": daypart_for(key, dayparts),
                    "data_origin": "derived",
                    "generation_method": GENERATION_METHOD,
                    "generation_version": GENERATION_VERSION,
                    "etl_run_id": etl_run_id,
                }
            )


def build_dimensions(
    holidays: dict[date, list[dict[str, str]]],
    staffed_hours: dict[str, list[str]],
    dayparts: dict[str, list[str]],
    etl_run_id: str,
) -> dict[str, Path]:
    dim_date_path = OUTPUT_DIR / "dim_date.csv.gz"
    dim_time_path = OUTPUT_DIR / "dim_time_interval.csv.gz"
    dim_queue_path = OUTPUT_DIR / "dim_queue.csv.gz"
    dim_service_path = OUTPUT_DIR / "dim_service_type.csv.gz"
    holiday_dates = set(holidays)
    date_columns = [
        "date_key",
        "calendar_date",
        "day_of_week_iso",
        "day_name",
        "day_of_month",
        "day_of_year",
        "week_of_year",
        "week_start_date",
        "month_number",
        "month_name",
        "quarter_number",
        "year_number",
        "is_weekend",
        "is_operating_day",
        "is_holiday",
        "holiday_name",
        "holiday_type",
        "is_major_holiday",
        "is_calendar_day_before_holiday",
        "is_calendar_day_after_holiday",
        "holiday_data_origin",
        "holiday_source_reference",
        "is_dst_transition_day",
        "data_origin",
        "generation_method",
        "generation_version",
        "etl_run_id",
    ]
    date_file, date_writer = csv_gzip_writer(dim_date_path, date_columns)
    with date_file:
        for day in date_range(START_DATE, END_DATE):
            day_holidays = holidays.get(day, [])
            transition_day = any(
                interval_time_metadata(day, f"{slot // 2:02d}{(slot % 2) * 30:02d}")[
                    "dst_transition"
                ]
                for slot in range(48)
            )
            date_writer.writerow(
                {
                    "date_key": day.strftime("%Y%m%d"),
                    "calendar_date": day.isoformat(),
                    "day_of_week_iso": day.isoweekday(),
                    "day_name": day.strftime("%A"),
                    "day_of_month": day.day,
                    "day_of_year": day.timetuple().tm_yday,
                    "week_of_year": day.isocalendar().week,
                    "week_start_date": (day - timedelta(days=day.weekday())).isoformat(),
                    "month_number": day.month,
                    "month_name": day.strftime("%B"),
                    "quarter_number": (day.month - 1) // 3 + 1,
                    "year_number": day.year,
                    "is_weekend": bool_text(day.weekday() in {4, 5}),
                    "is_operating_day": bool_text(
                        any(
                            is_operating_interval(
                                day,
                                f"{slot // 2:02d}{(slot % 2) * 30:02d}",
                                staffed_hours,
                            )
                            for slot in range(48)
                        )
                    ),
                    "is_holiday": bool_text(bool(day_holidays)),
                    "holiday_name": ";".join(
                        sorted({item["holiday_name"] for item in day_holidays})
                    ),
                    "holiday_type": ";".join(
                        sorted({item["holiday_type"] for item in day_holidays})
                    ),
                    "is_major_holiday": bool_text(
                        any(item["is_major"] == "true" for item in day_holidays)
                    ),
                    "is_calendar_day_before_holiday": bool_text(
                        day + timedelta(days=1) in holiday_dates
                    ),
                    "is_calendar_day_after_holiday": bool_text(
                        day - timedelta(days=1) in holiday_dates
                    ),
                    "holiday_data_origin": (
                        "external_reference" if day_holidays else ""
                    ),
                    "holiday_source_reference": (
                        HOLIDAY_REFERENCE if day_holidays else ""
                    ),
                    "is_dst_transition_day": bool_text(transition_day),
                    "data_origin": "derived",
                    "generation_method": GENERATION_METHOD,
                    "generation_version": GENERATION_VERSION,
                    "etl_run_id": etl_run_id,
                }
            )

    build_dim_time_interval(dim_time_path, dayparts, etl_run_id)

    queue_columns = [
        "queue_id",
        "queue_name",
        "channel",
        "direction",
        "timezone",
        "is_active",
        "valid_from",
        "valid_to",
        "data_origin",
        "generation_method",
        "generation_version",
        "etl_run_id",
    ]
    queue_file, queue_writer = csv_gzip_writer(dim_queue_path, queue_columns)
    with queue_file:
        queue_writer.writerow(
            {
                "queue_id": QUEUE_ID,
                "queue_name": "Inbound Support (MVP aggregate)",
                "channel": CHANNEL,
                "direction": DIRECTION,
                "timezone": TIMEZONE_NAME,
                "is_active": "true",
                "valid_from": START_DATE.isoformat(),
                "valid_to": END_DATE.isoformat(),
                "data_origin": "project_assumption",
                "generation_method": GENERATION_METHOD,
                "generation_version": GENERATION_VERSION,
                "etl_run_id": etl_run_id,
            }
        )

    service_columns = [
        "service_type_code",
        "service_type_name",
        "queue_id",
        "is_valid",
        "valid_from",
        "valid_to",
        "data_origin",
        "source_reference",
        "generation_method",
        "generation_version",
        "etl_run_id",
    ]
    service_file, service_writer = csv_gzip_writer(dim_service_path, service_columns)
    with service_file:
        for code, name in sorted(SERVICE_TYPE_LABELS.items()):
            service_writer.writerow(
                {
                    "service_type_code": code,
                    "service_type_name": name,
                    "queue_id": QUEUE_ID,
                    "is_valid": "true",
                    "valid_from": START_DATE.isoformat(),
                    "valid_to": END_DATE.isoformat(),
                    "data_origin": "source_observed",
                    "source_reference": SOURCE_REFERENCE,
                    "generation_method": GENERATION_METHOD,
                    "generation_version": GENERATION_VERSION,
                    "etl_run_id": etl_run_id,
                }
            )
    return {
        "dim_date": dim_date_path,
        "dim_time_interval": dim_time_path,
        "dim_queue": dim_queue_path,
        "dim_service_type": dim_service_path,
    }


def coverage_status(offered: int, raw: int, operating: bool) -> tuple[str, str]:
    if offered > 0:
        return "observed_with_calls", ""
    if raw > 0:
        return "observed_excluded_only", "all_source_records_excluded_or_quarantined"
    if operating:
        return "zero_filled_operating", "complete_archive_no_call"
    return "zero_filled_closed", "complete_archive_no_call_outside_staffed_hours"


def build_facts(
    queue_metrics: dict[tuple[str, str], dict[str, str]],
    service_metrics: dict[tuple[str, str, str], Counter[str]],
    demand_metrics: dict[tuple[str, str], Counter[str]],
    raw_counts: dict[tuple[str, str], Counter[str]],
    staffed_hours: dict[str, list[str]],
    etl_run_id: str,
) -> tuple[dict[str, Path], Counter[str]]:
    queue_path = OUTPUT_DIR / "fact_queue_interval_complete.csv.gz"
    service_path = OUTPUT_DIR / "fact_service_type_interval.csv.gz"
    queue_file, queue_writer = csv_gzip_writer(queue_path, QUEUE_COLUMNS)
    service_file, service_writer = csv_gzip_writer(
        service_path, SERVICE_INTERVAL_COLUMNS
    )
    counts: Counter[str] = Counter()
    with queue_file, service_file:
        for day in date_range(START_DATE, END_DATE):
            for slot in range(48):
                key = f"{slot // 2:02d}{(slot % 2) * 30:02d}"
                grain = (day.strftime("%Y%m%d"), key)
                observed = queue_metrics.get(grain, {})
                raw = raw_counts.get(grain, Counter())
                offered = int(observed.get("offered_calls", 0))
                demand = demand_metrics.get(grain, Counter())
                agent_demand = demand["agent_demand_calls"]
                answered = int(observed.get("answered_calls", 0))
                abandoned = int(observed.get("abandoned_calls", 0))
                short_abandons = int(observed.get("short_abandon_calls", 0))
                within_threshold = int(observed.get("answered_within_20s", 0))
                sl_denominator = offered - short_abandons
                operating = is_operating_interval(day, key, staffed_hours)
                status, zero_reason = coverage_status(
                    offered, raw["raw_record_count"], operating
                )
                times = interval_time_metadata(day, key)
                counts[f"coverage_{status}"] += 1
                counts[f"dst_{times['dst_status']}"] += 1
                counts["queue_rows"] += 1
                counts["queue_offered_calls"] += offered
                counts["queue_agent_demand_calls"] += agent_demand
                counts["queue_raw_records"] += raw["raw_record_count"]
                counts["queue_excluded_records"] += raw["excluded_record_count"]
                counts["queue_quarantine_records"] += raw[
                    "quarantine_record_count"
                ]
                audit = common_audit(
                    (
                        "source_observed_and_derived"
                        if offered or raw["raw_record_count"]
                        else "derived"
                    ),
                    etl_run_id,
                )
                queue_writer.writerow(
                    {
                        "date_key": grain[0],
                        "interval_key": key,
                        "queue_id": QUEUE_ID,
                        "local_interval_start": times["local_start"],
                        "local_interval_end": times["local_end"],
                        "interval_start_assumed": times["start_assumed"],
                        "interval_end_assumed": times["end_assumed"],
                        "interval_start_utc": times["start_utc"],
                        "interval_end_utc": times["end_utc"],
                        "actual_interval_seconds": times["actual_seconds"],
                        "source_timezone": TIMEZONE_NAME,
                        "interval_minutes": 30,
                        "channel": CHANNEL,
                        "direction": DIRECTION,
                        "raw_record_count": raw["raw_record_count"],
                        "excluded_record_count": raw["excluded_record_count"],
                        "quarantine_record_count": raw[
                            "quarantine_record_count"
                        ],
                        "has_source_records": bool_text(
                            raw["raw_record_count"] > 0
                        ),
                        "has_calls": bool_text(offered > 0),
                        "source_file_available": "true",
                        "source_date_covered": "true",
                        "interval_coverage_verified": "true",
                        "source_period_covered": "true",
                        "is_operating_interval": bool_text(operating),
                        "is_closed_interval": bool_text(not operating),
                        "coverage_status": status,
                        "zero_fill_reason": zero_reason,
                        "dst_transition_flag": bool_text(times["dst_transition"]),
                        "dst_status": times["dst_status"],
                        "offered_calls": offered,
                        "agent_demand_calls": agent_demand,
                        "answered_calls": answered,
                        "abandoned_calls": abandoned,
                        "queue_abandoned_calls": demand[
                            "queue_abandoned_calls"
                        ],
                        "vru_abandoned_calls": demand["vru_abandoned_calls"],
                        "short_abandon_calls": short_abandons,
                        "answered_within_20s": within_threshold,
                        "service_level_denominator": sl_denominator,
                        "service_level_rate": (
                            round(within_threshold / sl_denominator, 6)
                            if sl_denominator
                            else ""
                        ),
                        "total_wait_seconds": int(
                            observed.get("total_wait_seconds", 0)
                        ),
                        "avg_wait_seconds": observed.get("avg_wait_seconds", ""),
                        "aht_eligible_calls": int(
                            observed.get("aht_eligible_calls", 0)
                        ),
                        "total_service_seconds_for_aht": int(
                            observed.get("total_service_seconds_for_aht", 0)
                        ),
                        "aht_proxy_seconds": observed.get(
                            "aht_proxy_seconds", ""
                        ),
                        **audit,
                    }
                )

                for code, name in sorted(SERVICE_TYPE_LABELS.items()):
                    service_bucket = service_metrics.get(
                        (grain[0], key, code), Counter()
                    )
                    service_offered = service_bucket["offered_calls"]
                    aht_count = service_bucket["valid_for_aht_calls"]
                    counts["service_rows"] += 1
                    counts["service_offered_calls"] += service_offered
                    counts["service_agent_demand_calls"] += service_bucket[
                        "agent_demand_calls"
                    ]
                    service_writer.writerow(
                        {
                            "date_key": grain[0],
                            "interval_key": key,
                            "service_type_code": code,
                            "service_type_name": name,
                            "queue_id": QUEUE_ID,
                            "local_interval_start": times["local_start"],
                            "source_timezone": TIMEZONE_NAME,
                            "coverage_status": status,
                            "is_operating_interval": bool_text(operating),
                            "offered_calls": service_offered,
                            "agent_demand_calls": service_bucket[
                                "agent_demand_calls"
                            ],
                            "answered_calls": service_bucket["answered_calls"],
                            "abandoned_calls": service_bucket[
                                "abandoned_calls"
                            ],
                            "queue_abandoned_calls": service_bucket[
                                "queue_abandoned_calls"
                            ],
                            "vru_abandoned_calls": service_bucket[
                                "vru_abandoned_calls"
                            ],
                            "short_abandon_calls": service_bucket[
                                "short_abandon_calls"
                            ],
                            "answered_within_20s": service_bucket[
                                "answered_within_20s"
                            ],
                            "valid_for_aht_calls": aht_count,
                            "wait_seconds_sum": service_bucket[
                                "wait_seconds_sum"
                            ],
                            "service_seconds_sum_for_aht": service_bucket[
                                "service_seconds_sum_for_aht"
                            ],
                            "aht_proxy_seconds": (
                                round(
                                    service_bucket[
                                        "service_seconds_sum_for_aht"
                                    ]
                                    / aht_count,
                                    3,
                                )
                                if aht_count
                                else ""
                            ),
                            "data_origin": (
                                "source_observed_aggregated_and_derived"
                                if service_offered
                                else "derived"
                            ),
                            "source_reference": SOURCE_REFERENCE,
                            "generation_method": GENERATION_METHOD,
                            "generation_version": GENERATION_VERSION,
                            "etl_run_id": etl_run_id,
                        }
                    )
    return {
        "fact_queue_interval_complete": queue_path,
        "fact_service_type_interval": service_path,
    }, counts


def report_outputs(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    return {
        path.name: {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in paths
    }


def write_report(
    paths: dict[str, Path], counts: Counter[str], etl_run_id: str
) -> None:
    report = {
        "report_version": GENERATION_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "etl_run_id": etl_run_id,
        "source_coverage_basis": {
            "statement": "Technion documentation states the data archives all calls over 1999 and the VRU operated 24/7.",
            "source_reference": SOURCE_REFERENCE,
            "monthly_files_verified": len(MONTH_FILES),
        },
        "summary": dict(sorted(counts.items())),
        "invariants": {
            "queue_rows_expected": 365 * 48,
            "service_rows_expected": 365 * 48 * len(SERVICE_TYPE_LABELS),
            "clean_calls_expected": 440_844,
            "raw_rows_expected": 444_448,
            "excluded_rows_expected": 3_599,
            "quarantine_rows_expected": 5,
        },
        "holiday_reference": {
            "source": HOLIDAY_REFERENCE,
            "interpretation": "Calendar observance only; not proof of closure or operational impact.",
        },
        "outputs": report_outputs(paths.values()),
    }
    json_path = REPORT_DIR / "foundation_marts_reconciliation.json"
    md_path = REPORT_DIR / "foundation_marts_reconciliation.md"
    checksum_path = REPORT_DIR / "foundation_marts_reconciliation.sha256"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Foundation marts reconciliation",
        "",
        f"ETL run: `{etl_run_id}`",
        "",
        "## Core reconciliation",
        "",
        f"- Queue interval rows: **{counts['queue_rows']:,}**",
        f"- Service-type interval rows: **{counts['service_rows']:,}**",
        f"- Offered calls in queue mart: **{counts['queue_offered_calls']:,}**",
        f"- Offered calls in service mart: **{counts['service_offered_calls']:,}**",
        f"- Agent-demand calls used for staffing forecast: **{counts['queue_agent_demand_calls']:,}**",
        f"- Raw records assigned to intervals: **{counts['queue_raw_records']:,}**",
        f"- Excluded records assigned: **{counts['queue_excluded_records']:,}**",
        f"- Quarantine records assigned: **{counts['queue_quarantine_records']:,}**",
        "",
        "## Coverage",
        "",
        f"- Observed with clean calls: **{counts['coverage_observed_with_calls']:,}**",
        f"- Observed excluded/quarantine only: **{counts['coverage_observed_excluded_only']:,}**",
        f"- Zero-filled operating: **{counts['coverage_zero_filled_operating']:,}**",
        f"- Zero-filled closed: **{counts['coverage_zero_filled_closed']:,}**",
        "",
        "Holiday flags are external calendar references and do not imply closure.",
        "Ambiguous/nonexistent local DST times keep UTC fields null.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    checksum_path.write_text(
        f"{sha256(json_path)}  {json_path.name}\n"
        f"{sha256(md_path)}  {md_path.name}\n",
        encoding="ascii",
    )


def main() -> None:
    config = load_config()
    baseline = load_raw_baseline()
    baseline_hash = hashlib.sha256(
        BASELINE_PATH.read_bytes()
    ).hexdigest()[:12]
    etl_run_id = f"foundation_v1_{baseline_hash}"
    if baseline["summary"]["total_raw_rows"] != 444_448:
        raise RuntimeError("Unexpected raw baseline row count")

    holidays = load_holidays()
    queue_metrics = load_queue_metrics()
    service_metrics, demand_metrics = load_call_metrics()
    raw_counts = raw_interval_counts()
    staffed_hours = config["scope"]["agent_staffed_hours"]
    dayparts = config["scope"]["dayparts"]
    dimension_paths = build_dimensions(
        holidays, staffed_hours, dayparts, etl_run_id
    )
    fact_paths, counts = build_facts(
        queue_metrics,
        service_metrics,
        demand_metrics,
        raw_counts,
        staffed_hours,
        etl_run_id,
    )

    expected = {
        "queue_rows": 365 * 48,
        "service_rows": 365 * 48 * len(SERVICE_TYPE_LABELS),
        "queue_offered_calls": 440_844,
        "service_offered_calls": 440_844,
        "queue_raw_records": 444_448,
        "queue_excluded_records": 3_599,
        "queue_quarantine_records": 5,
    }
    for metric, expected_value in expected.items():
        if counts[metric] != expected_value:
            raise RuntimeError(
                f"Foundation reconciliation failed for {metric}: "
                f"expected {expected_value}, got {counts[metric]}"
            )
    if counts["queue_agent_demand_calls"] != counts["service_agent_demand_calls"]:
        raise RuntimeError("Agent-demand calls do not reconcile across grains")

    output_paths = {**dimension_paths, **fact_paths}
    write_report(output_paths, counts, etl_run_id)
    print(
        f"Built {counts['queue_rows']:,} queue intervals and "
        f"{counts['service_rows']:,} service intervals"
    )
    print(
        f"Reconciled offered={counts['queue_offered_calls']:,}, "
        f"raw={counts['queue_raw_records']:,}, "
        f"excluded={counts['queue_excluded_records']:,}, "
        f"quarantine={counts['queue_quarantine_records']:,}"
    )
    print(f"Outputs: {OUTPUT_DIR.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
