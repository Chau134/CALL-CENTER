"""Capture a reproducible, privacy-safe baseline before ETL.

The generated JSON is the machine-readable evidence used for post-ETL
reconciliation. The Markdown file is a human-readable snapshot. Raw source
files are read but never changed.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from inspect_raw_data import DURATION_COLUMNS, EXPECTED_COLUMNS, RAW_DIR, read_source_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"
JSON_REPORT = REPORT_DIR / "raw_baseline.json"
MARKDOWN_REPORT = REPORT_DIR / "raw_baseline.md"
CHECKSUM_REPORT = REPORT_DIR / "raw_baseline.sha256"
EXPECTED_OUTCOMES = {"AGENT", "HANG", "PHANTOM"}
EXPECTED_SERVICE_TYPES = {"PS", "PE", "IN", "NE", "NW", "TT"}
EXPECTED_PRIORITIES = {"0", "1", "2"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def malformed_line_details(path: Path) -> list[dict[str, int]]:
    issues: list[dict[str, int]] = []
    with path.open(encoding="ascii", newline="") as source_file:
        next(source_file)
        for line_number, line in enumerate(source_file, start=2):
            field_count = line.rstrip("\r\n").count("\t") + 1
            if field_count != len(EXPECTED_COLUMNS):
                issues.append(
                    {
                        "line_number": line_number,
                        "field_count": field_count,
                        "expected_field_count": len(EXPECTED_COLUMNS),
                    }
                )
    return issues


def sorted_counter(counter: Counter[str]) -> dict[str, int]:
    return dict(sorted(counter.items()))


def profile_file(path: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    frame = read_source_file(path)
    malformed = malformed_line_details(path)
    parsed_dates = pd.to_datetime(
        "19" + frame["date"].str.zfill(6), format="%Y%m%d", errors="coerce"
    )

    invalid_duration: dict[str, int] = {}
    negative_duration: dict[str, int] = {}
    for column in DURATION_COLUMNS:
        numeric = pd.to_numeric(frame[column], errors="coerce")
        invalid_duration[column] = int(numeric.isna().sum())
        negative_duration[column] = int((numeric < 0).sum())

    blank_counts = {
        column: int(frame[column].str.strip().eq("").sum())
        for column in EXPECTED_COLUMNS
    }

    profile = {
        "file_name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "row_count": len(frame),
        "column_count": len(frame.columns),
        "schema_matches_expected": frame.columns.tolist() == EXPECTED_COLUMNS,
        "date_min": parsed_dates.min().date().isoformat(),
        "date_max": parsed_dates.max().date().isoformat(),
        "outcome_counts_raw": sorted_counter(Counter(frame["outcome"].str.strip())),
        "service_type_counts_raw": sorted_counter(Counter(frame["type"].str.strip())),
        "priority_counts_raw": sorted_counter(Counter(frame["priority"].str.strip())),
        "blank_counts": blank_counts,
        "invalid_duration_counts": invalid_duration,
        "negative_duration_counts": negative_duration,
        "duplicate_vru_line_call_id_rows": int(
            frame.duplicated(subset=["vru+line", "call_id"], keep=False).sum()
        ),
        "malformed_delimiter_rows": malformed,
    }
    return profile, frame


def build_baseline() -> dict[str, Any]:
    paths = sorted(RAW_DIR.glob("*1999.txt"))
    if not paths:
        raise FileNotFoundError(f"No extracted monthly files found in {RAW_DIR}")

    file_profiles: list[dict[str, Any]] = []
    total_rows = 0
    total_malformed = 0
    outcome_counts: Counter[str] = Counter()
    service_type_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    invalid_duration: Counter[str] = Counter()
    negative_duration: Counter[str] = Counter()
    agent_labels: set[str] = set()
    all_dates: list[pd.Series] = []

    for path in paths:
        profile, frame = profile_file(path)
        file_profiles.append(profile)
        total_rows += len(frame)
        total_malformed += len(profile["malformed_delimiter_rows"])
        outcome_counts.update(frame["outcome"].str.strip())
        service_type_counts.update(frame["type"].str.strip())
        priority_counts.update(frame["priority"].str.strip())
        invalid_duration.update(profile["invalid_duration_counts"])
        negative_duration.update(profile["negative_duration_counts"])
        agent_labels.update(
            value
            for value in frame["server"].str.strip().unique()
            if value and value != "NO_SERVER"
        )
        all_dates.append(
            pd.to_datetime(
                "19" + frame["date"].str.zfill(6),
                format="%Y%m%d",
                errors="coerce",
            )
        )

    combined_dates = pd.concat(all_dates, ignore_index=True)
    unexpected_outcomes = {
        key: value
        for key, value in sorted_counter(outcome_counts).items()
        if key not in EXPECTED_OUTCOMES
    }
    unexpected_service_types = {
        key: value
        for key, value in sorted_counter(service_type_counts).items()
        if key not in EXPECTED_SERVICE_TYPES
    }
    unexpected_priorities = {
        key: value
        for key, value in sorted_counter(priority_counts).items()
        if key not in EXPECTED_PRIORITIES
    }

    archive_path = RAW_DIR.parent / "AnonymousBank.rar"
    documentation_path = RAW_DIR.parent / "documentation.pdf"
    source_artifacts = {}
    for path in (archive_path, documentation_path):
        if path.exists():
            source_artifacts[path.name] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }

    return {
        "baseline_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Pre-ETL reconciliation evidence; contains aggregate data only.",
        "source": {
            "dataset": "Technion Anonymous Bank Call-Center Data",
            "period": "1999-01-01/1999-12-31",
            "raw_directory": str(RAW_DIR.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "artifacts": source_artifacts,
        },
        "expected_schema": EXPECTED_COLUMNS,
        "summary": {
            "monthly_file_count": len(paths),
            "total_raw_rows": total_rows,
            "structurally_well_formed_rows": total_rows - total_malformed,
            "malformed_delimiter_rows": total_malformed,
            "date_min": combined_dates.min().date().isoformat(),
            "date_max": combined_dates.max().date().isoformat(),
            "distinct_agent_labels_names_suppressed": len(agent_labels),
            "outcome_counts_raw": sorted_counter(outcome_counts),
            "service_type_counts_raw": sorted_counter(service_type_counts),
            "priority_counts_raw": sorted_counter(priority_counts),
            "unexpected_outcomes": unexpected_outcomes,
            "unexpected_service_types": unexpected_service_types,
            "unexpected_priorities": unexpected_priorities,
            "invalid_duration_counts": sorted_counter(invalid_duration),
            "negative_duration_counts": sorted_counter(negative_duration),
            "duplicate_vru_line_call_id_rows_within_month": sum(
                profile["duplicate_vru_line_call_id_rows"] for profile in file_profiles
            ),
        },
        "files": file_profiles,
        "privacy": {
            "contains_customer_ids": False,
            "contains_agent_names": False,
            "note": "Only counts and hashes are stored; raw identifiers are suppressed.",
        },
    }


def markdown_report(baseline: dict[str, Any]) -> str:
    summary = baseline["summary"]
    lines = [
        "# Raw Data Baseline — Before ETL",
        "",
        f"Generated at UTC: `{baseline['generated_at_utc']}`",
        "",
        "This snapshot is the reconciliation evidence for the unmodified Technion source. It contains no customer IDs or agent names.",
        "",
        "## Dataset totals",
        "",
        f"- Monthly files: **{summary['monthly_file_count']}**",
        f"- Total raw rows: **{summary['total_raw_rows']:,}**",
        f"- Structurally well-formed rows: **{summary['structurally_well_formed_rows']:,}**",
        f"- Malformed delimiter rows: **{summary['malformed_delimiter_rows']:,}**",
        f"- Date coverage: **{summary['date_min']} to {summary['date_max']}**",
        f"- Distinct agent labels, names suppressed: **{summary['distinct_agent_labels_names_suppressed']:,}**",
        "",
        "## Raw distributions",
        "",
        f"- Outcomes: `{json.dumps(summary['outcome_counts_raw'], sort_keys=True)}`",
        f"- Service types: `{json.dumps(summary['service_type_counts_raw'], sort_keys=True)}`",
        f"- Priorities: `{json.dumps(summary['priority_counts_raw'], sort_keys=True)}`",
        "",
        "## Quality evidence",
        "",
        f"- Unexpected outcomes: `{json.dumps(summary['unexpected_outcomes'], sort_keys=True)}`",
        f"- Unexpected service types: `{json.dumps(summary['unexpected_service_types'], sort_keys=True)}`",
        f"- Unexpected priorities: `{json.dumps(summary['unexpected_priorities'], sort_keys=True)}`",
        f"- Invalid durations: `{json.dumps(summary['invalid_duration_counts'], sort_keys=True)}`",
        f"- Negative durations: `{json.dumps(summary['negative_duration_counts'], sort_keys=True)}`",
        f"- Duplicate source-key rows within month: **{summary['duplicate_vru_line_call_id_rows_within_month']:,}**",
        "",
        "## Monthly files",
        "",
        "| File | Rows | Bytes | Malformed | SHA-256 |",
        "|---|---:|---:|---:|---|",
    ]
    for profile in baseline["files"]:
        lines.append(
            f"| `{profile['file_name']}` | {profile['row_count']:,} | "
            f"{profile['size_bytes']:,} | {len(profile['malformed_delimiter_rows'])} | "
            f"`{profile['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Reconciliation identity",
            "",
            "After ETL, the following identity must be explained exactly:",
            "",
            "```text",
            "total_raw_rows",
            "= clean_rows",
            "+ excluded_rows",
            "+ quarantine_rows",
            "```",
            "",
            "No row may disappear without an exclusion or quarantine reason.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    baseline = build_baseline()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    MARKDOWN_REPORT.write_text(markdown_report(baseline), encoding="utf-8")
    CHECKSUM_REPORT.write_text(
        f"{sha256(JSON_REPORT)}  {JSON_REPORT.name}\n"
        f"{sha256(MARKDOWN_REPORT)}  {MARKDOWN_REPORT.name}\n",
        encoding="ascii",
    )
    print(f"Wrote {JSON_REPORT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {MARKDOWN_REPORT.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {CHECKSUM_REPORT.relative_to(PROJECT_ROOT)}")
    print(f"Captured {baseline['summary']['total_raw_rows']:,} raw rows")


if __name__ == "__main__":
    main()
