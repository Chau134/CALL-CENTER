"""Load processed marts into PostgreSQL analytics tables transactionally."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

try:
    from .bootstrap_database import connection_kwargs, load_settings
except ImportError:  # Support direct execution.
    from bootstrap_database import connection_kwargs, load_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MART_DIR = PROJECT_ROOT / "data" / "processed" / "technion"
SCHEMA_SQL_PATH = PROJECT_ROOT / "sql" / "01_analytics_schema.sql"
VIEW_SQL_PATH = PROJECT_ROOT / "sql" / "02_powerbi_views.sql"
LOADER_VERSION = "1.0.0"


@dataclass(frozen=True)
class MartSpec:
    filename: str
    table_name: str

    @property
    def path(self) -> Path:
        return MART_DIR / self.filename


MART_SPECS = (
    MartSpec("dim_date.csv.gz", "dim_date"),
    MartSpec("dim_time_interval.csv.gz", "dim_time_interval"),
    MartSpec("dim_queue.csv.gz", "dim_queue"),
    MartSpec("dim_service_type.csv.gz", "dim_service_type"),
    MartSpec("fact_queue_interval_complete.csv.gz", "fact_queue_interval_complete"),
    MartSpec("fact_service_type_interval.csv.gz", "fact_service_type_interval"),
    MartSpec("fact_forecast_interval.csv.gz", "fact_forecast_interval"),
    MartSpec("fact_model_evaluation.csv.gz", "fact_model_evaluation"),
    MartSpec("fact_staffing_requirement.csv.gz", "fact_staffing_requirement"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_copy_value(value: Any) -> Any:
    """Convert pandas/numpy values to types psycopg COPY can adapt."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def database_columns(connection: psycopg.Connection[Any], table_name: str) -> list[str]:
    rows = connection.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'analytics' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    ).fetchall()
    if not rows:
        raise RuntimeError(f"Missing analytics table: {table_name}")
    return [row[0] for row in rows]


def truncate_managed_marts(connection: psycopg.Connection[Any]) -> None:
    identifiers = [
        sql.SQL("{}.{}").format(sql.Identifier("analytics"), sql.Identifier(spec.table_name))
        for spec in MART_SPECS
    ]
    statement = sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY").format(
        sql.SQL(", ").join(identifiers)
    )
    connection.execute(statement)


def copy_mart(
    connection: psycopg.Connection[Any], spec: MartSpec
) -> tuple[int, str]:
    if not spec.path.exists():
        raise FileNotFoundError(f"Missing mart source: {spec.path}")
    frame = pd.read_csv(spec.path)
    columns = frame.columns.tolist()
    expected_columns = database_columns(connection, spec.table_name)
    if columns != expected_columns:
        raise RuntimeError(
            f"Schema mismatch for {spec.filename}: source={columns}, "
            f"database={expected_columns}"
        )

    copy_statement = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
        sql.Identifier("analytics"),
        sql.Identifier(spec.table_name),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
    )
    with connection.cursor() as cursor:
        with cursor.copy(copy_statement) as copy:
            for row in frame.itertuples(index=False, name=None):
                copy.write_row(tuple(normalize_copy_value(value) for value in row))
    return len(frame), sha256(spec.path)


def load_marts() -> dict[str, int]:
    settings = load_settings()
    schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    view_sql = VIEW_SQL_PATH.read_text(encoding="utf-8")
    row_counts: dict[str, int] = {}
    checksums: dict[str, str] = {}

    with psycopg.connect(
        **connection_kwargs(settings, settings.database)
    ) as connection:
        connection.execute(schema_sql, prepare=False)
        truncate_managed_marts(connection)
        for spec in MART_SPECS:
            count, checksum = copy_mart(connection, spec)
            row_counts[spec.table_name] = count
            checksums[spec.filename] = checksum
            print(f"Loaded analytics.{spec.table_name}: {count:,} rows")
        connection.execute(view_sql, prepare=False)
        connection.execute(
            """
            INSERT INTO analytics.mart_load_audit (
                loader_version, source_directory, table_row_counts, source_sha256
            ) VALUES (%s, %s, %s, %s)
            """,
            (
                LOADER_VERSION,
                str(MART_DIR),
                Jsonb(row_counts),
                Jsonb(checksums),
            ),
        )

    print(f"Committed {sum(row_counts.values()):,} rows across {len(row_counts)} marts")
    print("Created/refreshed Power BI serving views in schema analytics")
    return row_counts


def main() -> None:
    counts = load_marts()
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
