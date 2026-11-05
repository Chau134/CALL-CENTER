"""Inspect the extracted Technion files without printing sensitive values.

The command is read-only. It reports schemas, row counts, categorical counts,
date coverage, and basic duration-quality checks. Customer IDs and agent names
are never printed.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "technion" / "AnonymousBank"
EXPECTED_COLUMNS = [
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
DURATION_COLUMNS = ("vru_time", "q_time", "ser_time")


def read_source_file(path: Path) -> pd.DataFrame:
    """Read one tab-delimited source file without automatic type coercion."""
    return pd.read_csv(
        path,
        sep="\t",
        dtype="string",
        keep_default_na=False,
        encoding="ascii",
    )


def main() -> None:
    paths = sorted(RAW_DIR.glob("*1999.txt"))
    if not paths:
        raise FileNotFoundError(f"No extracted monthly files found in {RAW_DIR}")

    total_rows = 0
    outcome_counts: Counter[str] = Counter()
    service_type_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    agent_ids: set[str] = set()
    outcome_server_presence: Counter[str] = Counter()
    agent_outcome_zero_service = 0
    invalid_numeric = Counter()
    negative_duration = Counter()
    negative_vru_repairability: Counter[str] = Counter()
    duplicate_source_keys = 0
    malformed_lines: list[tuple[str, int, int]] = []
    minimum_date: pd.Timestamp | None = None
    maximum_date: pd.Timestamp | None = None

    print("Monthly files")
    for path in paths:
        with path.open(encoding="ascii", newline="") as source_file:
            next(source_file)
            for line_number, line in enumerate(source_file, start=2):
                field_count = line.rstrip("\r\n").count("\t") + 1
                if field_count != len(EXPECTED_COLUMNS):
                    malformed_lines.append((path.name, line_number, field_count))

        frame = read_source_file(path)
        schema_ok = frame.columns.tolist() == EXPECTED_COLUMNS
        print(f"- {path.name}: rows={len(frame):,}, columns={len(frame.columns)}, schema_ok={schema_ok}")
        if not schema_ok:
            raise ValueError(f"Unexpected schema in {path.name}: {frame.columns.tolist()}")

        total_rows += len(frame)
        outcome_counts.update(frame["outcome"].str.strip().replace("", "<blank>"))
        service_type_counts.update(frame["type"].str.strip().replace("", "<blank>"))
        priority_counts.update(frame["priority"].str.strip().replace("", "<blank>"))
        agent_ids.update(
            value
            for value in frame["server"].str.strip().unique()
            if value and value != "NO_SERVER"
        )
        server_present = frame["server"].str.strip().ne("") & frame["server"].str.strip().ne(
            "NO_SERVER"
        )
        outcome_server_presence.update(
            frame["outcome"].str.strip()
            + "|server_present="
            + server_present.astype("string")
        )
        service_numeric = pd.to_numeric(frame["ser_time"], errors="coerce")
        agent_outcome_zero_service += int(
            (frame["outcome"].str.strip().eq("AGENT") & service_numeric.eq(0)).sum()
        )

        duplicate_source_keys += int(
            frame.duplicated(subset=["vru+line", "call_id"], keep=False).sum()
        )

        parsed_dates = pd.to_datetime(
            "19" + frame["date"].str.zfill(6), format="%Y%m%d", errors="coerce"
        )
        valid_dates = parsed_dates.dropna()
        if not valid_dates.empty:
            file_min = valid_dates.min()
            file_max = valid_dates.max()
            minimum_date = file_min if minimum_date is None else min(minimum_date, file_min)
            maximum_date = file_max if maximum_date is None else max(maximum_date, file_max)

        for column in DURATION_COLUMNS:
            numeric = pd.to_numeric(frame[column], errors="coerce")
            invalid_numeric[column] += int(numeric.isna().sum())
            negative_duration[column] += int((numeric < 0).sum())

        vru_numeric = pd.to_numeric(frame["vru_time"], errors="coerce")
        for entry_text, exit_text in frame.loc[
            vru_numeric < 0, ["vru_entry", "vru_exit"]
        ].itertuples(index=False, name=None):
            try:
                entry = pd.to_timedelta(entry_text).total_seconds()
                exit_ = pd.to_timedelta(exit_text).total_seconds()
            except (TypeError, ValueError):
                negative_vru_repairability["unparseable_timestamp"] += 1
                continue
            raw_difference = int(exit_ - entry)
            if raw_difference >= 0:
                negative_vru_repairability["repair_from_same_day_timestamps"] += 1
            elif raw_difference + 86_400 <= 3_600:
                negative_vru_repairability["repair_as_midnight_rollover"] += 1
            else:
                negative_vru_repairability["not_safely_repairable"] += 1

    print("\nSafe profile")
    print(f"- files: {len(paths)}")
    print(f"- total rows: {total_rows:,}")
    print(f"- date coverage: {minimum_date.date()} to {maximum_date.date()}")
    print(f"- distinct agent labels (names suppressed): {len(agent_ids):,}")
    print(f"- duplicate rows by vru_line + call_id within a monthly file: {duplicate_source_keys:,}")
    print(f"- outcomes: {dict(sorted(outcome_counts.items()))}")
    print(f"- service types: {dict(sorted(service_type_counts.items()))}")
    print(f"- priorities: {dict(sorted(priority_counts.items()))}")
    print(f"- invalid duration values: {dict(invalid_numeric)}")
    print(f"- negative duration values: {dict(negative_duration)}")
    print(f"- negative VRU repairability: {dict(sorted(negative_vru_repairability.items()))}")
    print(f"- outcome by server presence: {dict(sorted(outcome_server_presence.items()))}")
    print(f"- AGENT outcomes with zero service time: {agent_outcome_zero_service:,}")
    print(f"- malformed delimiter rows: {len(malformed_lines):,}")
    for file_name, line_number, field_count in malformed_lines:
        print(
            f"  - {file_name}: line={line_number:,}, "
            f"fields={field_count}, expected={len(EXPECTED_COLUMNS)}"
        )


if __name__ == "__main__":
    main()
