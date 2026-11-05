"""Validate PostgreSQL grain and KPI assumptions used by the Power BI plan."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg

try:
    from .bootstrap_database import connection_kwargs, load_settings
    from .transform_calls import PROJECT_ROOT
except ImportError:  # Support direct execution.
    from bootstrap_database import connection_kwargs, load_settings
    from transform_calls import PROJECT_ROOT


REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"
REPORT_JSON = REPORT_DIR / "powerbi_model_readiness.json"
REPORT_MD = REPORT_DIR / "powerbi_model_readiness.md"
REPORT_SHA = REPORT_DIR / "powerbi_model_readiness.sha256"


def scalar(connection: psycopg.Connection[Any], query: str) -> Any:
    return connection.execute(query).fetchone()[0]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    settings = load_settings()
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    with psycopg.connect(
        **connection_kwargs(settings, settings.database)
    ) as connection:
        dimension_queries = {
            "dim_date_key_unique": (
                "analytics.dim_date",
                "date_key",
            ),
            "dim_time_interval_key_unique": (
                "analytics.dim_time_interval",
                "interval_key",
            ),
            "dim_queue_key_unique": (
                "analytics.dim_queue",
                "queue_id",
            ),
            "dim_service_type_key_unique": (
                "analytics.dim_service_type",
                "service_type_code",
            ),
        }
        for check_name, (table_name, key_name) in dimension_queries.items():
            result = connection.execute(
                f"""
                SELECT COUNT(*), COUNT(DISTINCT {key_name}),
                       COUNT(*) FILTER (WHERE {key_name} IS NULL)
                FROM {table_name}
                """
            ).fetchone()
            details[check_name] = {
                "rows": result[0],
                "distinct_keys": result[1],
                "null_keys": result[2],
            }
            checks[check_name] = result[0] == result[1] and result[2] == 0

        forecast = connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT (target_date_key, target_interval_key, queue_id)),
                COUNT(DISTINCT forecast_run_id),
                COUNT(DISTINCT model_name)
            FROM analytics.fact_forecast_interval
            WHERE is_selected_model
            """
        ).fetchone()
        details["selected_forecast"] = {
            "rows": forecast[0],
            "distinct_targets": forecast[1],
            "runs": forecast[2],
            "models": forecast[3],
        }
        checks["selected_forecast_targets_unique"] = (
            forecast[0] == forecast[1] == 2_016
            and forecast[2] == 6
            and forecast[3] == 1
        )

        evaluation = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT model_name),
                   COUNT(*) FILTER (WHERE is_selected_model)
            FROM analytics.fact_model_evaluation
            WHERE backtest_fold = 'ALL' AND evaluation_scope = 'overall'
            """
        ).fetchone()
        details["aggregate_evaluation"] = {
            "rows": evaluation[0],
            "models": evaluation[1],
            "selected_rows": evaluation[2],
        }
        checks["one_aggregate_evaluation_per_model"] = evaluation == (4, 4, 1)

        staffing = connection.execute(
            """
            SELECT
                COUNT(*),
                COUNT(DISTINCT (target_date_key, target_interval_key, queue_id)),
                COUNT(DISTINCT forecast_run_id), COUNT(DISTINCT model_name),
                COUNT(*) FILTER (WHERE required_scheduled_agents > 0),
                MAX(required_productive_agents), MAX(required_scheduled_agents),
                SUM(workload_hours)
            FROM analytics.fact_staffing_requirement
            """
        ).fetchone()
        details["staffing"] = {
            "rows": staffing[0],
            "distinct_targets": staffing[1],
            "runs": staffing[2],
            "models": staffing[3],
            "intervals_requiring_staff": staffing[4],
            "peak_productive_agents": staffing[5],
            "peak_scheduled_agents": staffing[6],
            "planned_workload_hours": float(staffing[7]),
        }
        checks["staffing_targets_unique"] = (
            staffing[0] == staffing[1] == 336
            and staffing[2] == 1
            and staffing[3] == 1
            and staffing[4] == 205
            and staffing[5] == 15
            and staffing[6] == 22
        )

        queue_totals = connection.execute(
            """
            SELECT SUM(offered_calls), SUM(agent_demand_calls),
                   SUM(answered_calls), SUM(abandoned_calls)
            FROM analytics.fact_queue_interval_complete
            """
        ).fetchone()
        service_totals = connection.execute(
            """
            SELECT SUM(offered_calls), SUM(agent_demand_calls),
                   SUM(answered_calls), SUM(abandoned_calls)
            FROM analytics.fact_service_type_interval
            """
        ).fetchone()
        details["queue_totals"] = list(map(int, queue_totals))
        details["service_totals"] = list(map(int, service_totals))
        checks["service_type_reconciles_to_queue"] = queue_totals == service_totals
        checks["queue_benchmarks_match"] = tuple(map(int, queue_totals)) == (
            440_844,
            417_149,
            353_143,
            87_701,
        )

        kpis = connection.execute(
            """
            SELECT
                SUM(answered_calls)::numeric / NULLIF(SUM(offered_calls), 0),
                SUM(abandoned_calls)::numeric / NULLIF(SUM(offered_calls), 0),
                SUM(answered_within_20s)::numeric
                    / NULLIF(SUM(service_level_denominator), 0),
                SUM(total_service_seconds_for_aht)::numeric
                    / NULLIF(SUM(aht_eligible_calls), 0)
            FROM analytics.fact_queue_interval_complete
            """
        ).fetchone()
        details["executive_kpis"] = {
            "answer_rate": float(kpis[0]),
            "abandon_rate": float(kpis[1]),
            "service_level": float(kpis[2]),
            "aht_proxy_seconds": float(kpis[3]),
        }
        checks["executive_kpis_available"] = all(value is not None for value in kpis)

        refresh_columns = connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'analytics'
              AND table_name = 'vw_powerbi_refresh_status'
            """
        ).fetchall()
        refresh_column_names = {row[0] for row in refresh_columns}
        required_refresh_columns = {
            "load_id",
            "loaded_at_utc",
            "table_row_counts",
            "source_sha256",
        }
        details["refresh_columns"] = sorted(refresh_column_names)
        checks["refresh_metadata_available"] = required_refresh_columns <= refresh_column_names
        checks["refresh_rows_available"] = scalar(
            connection, "SELECT COUNT(*) FROM analytics.vw_powerbi_refresh_status"
        ) > 0

    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise AssertionError(f"Power BI readiness checks failed: {', '.join(failed)}")

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": settings.database,
        "status": "passed",
        "checks": checks,
        "details": details,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Power BI model readiness",
        "",
        "Status: **passed**",
        f"Database: `{settings.database}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- [x] `{name}`" for name in checks)
    lines.extend(
        [
            "",
            "## Verified grains",
            "",
            f"- Selected forecast: {forecast[0]:,} rows / {forecast[1]:,} unique targets / {forecast[2]} runs.",
            f"- Staffing: {staffing[0]:,} rows / {staffing[1]:,} unique targets / {staffing[2]} run.",
            f"- Aggregate evaluation: {evaluation[0]} rows / {evaluation[1]} models / {evaluation[2]} selected row.",
            f"- Service-type totals reconcile to queue totals: {queue_totals[0]:,} offered calls.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_SHA.write_text(
        f"{sha256(REPORT_JSON)}  {REPORT_JSON.name}\n"
        f"{sha256(REPORT_MD)}  {REPORT_MD.name}\n",
        encoding="ascii",
    )
    print("Power BI model readiness validation passed")
    print(
        f"Selected forecast targets={forecast[1]:,}; staffing targets={staffing[1]:,}; "
        f"checks={len(checks)}"
    )


if __name__ == "__main__":
    main()
