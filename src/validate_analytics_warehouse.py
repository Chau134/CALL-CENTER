"""Reconcile PostgreSQL analytics tables and KPI views against source marts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg

try:
    from .bootstrap_database import connection_kwargs, load_settings
    from .load_analytics_marts import MART_SPECS, PROJECT_ROOT
except ImportError:  # Support direct execution.
    from bootstrap_database import connection_kwargs, load_settings
    from load_analytics_marts import MART_SPECS, PROJECT_ROOT


REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"
REPORT_JSON = REPORT_DIR / "postgres_warehouse_reconciliation.json"
REPORT_MD = REPORT_DIR / "postgres_warehouse_reconciliation.md"
REPORT_SHA = REPORT_DIR / "postgres_warehouse_reconciliation.sha256"

EXPECTED_VIEWS = {
    "vw_powerbi_queue_interval",
    "vw_kpi_daily_queue",
    "vw_kpi_service_type_daily",
    "vw_powerbi_forecast_interval",
    "vw_kpi_forecast_weekly_model",
    "vw_powerbi_model_evaluation",
    "vw_powerbi_staffing_interval",
    "vw_kpi_staffing_daily",
    "vw_powerbi_refresh_status",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def scalar(connection: psycopg.Connection[Any], query: str) -> Any:
    return connection.execute(query).fetchone()[0]


def main() -> None:
    source_counts = {
        spec.table_name: len(pd.read_csv(spec.path, usecols=[0])) for spec in MART_SPECS
    }
    settings = load_settings()
    with psycopg.connect(
        **connection_kwargs(settings, settings.database)
    ) as connection:
        database_counts = {
            spec.table_name: scalar(
                connection, f"SELECT COUNT(*) FROM analytics.{spec.table_name}"
            )
            for spec in MART_SPECS
        }
        assert database_counts == source_counts

        queue_totals = connection.execute(
            """
            SELECT
                SUM(offered_calls), SUM(agent_demand_calls), SUM(answered_calls),
                SUM(abandoned_calls), SUM(queue_abandoned_calls),
                SUM(vru_abandoned_calls)
            FROM analytics.fact_queue_interval_complete
            """
        ).fetchone()
        queue_totals_dict = dict(
            zip(
                (
                    "offered_calls",
                    "agent_demand_calls",
                    "answered_calls",
                    "abandoned_calls",
                    "queue_abandoned_calls",
                    "vru_abandoned_calls",
                ),
                map(int, queue_totals),
            )
        )
        assert queue_totals_dict["offered_calls"] == 440_844
        assert queue_totals_dict["agent_demand_calls"] == 417_149
        assert queue_totals_dict["offered_calls"] == (
            queue_totals_dict["answered_calls"] + queue_totals_dict["abandoned_calls"]
        )

        service_totals = connection.execute(
            """
            SELECT SUM(offered_calls), SUM(agent_demand_calls), SUM(answered_calls),
                   SUM(abandoned_calls)
            FROM analytics.fact_service_type_interval
            """
        ).fetchone()
        assert tuple(map(int, service_totals)) == (
            queue_totals_dict["offered_calls"],
            queue_totals_dict["agent_demand_calls"],
            queue_totals_dict["answered_calls"],
            queue_totals_dict["abandoned_calls"],
        )

        daily_totals = connection.execute(
            """
            SELECT SUM(offered_calls), SUM(agent_demand_calls), SUM(answered_calls),
                   SUM(abandoned_calls)
            FROM analytics.vw_kpi_daily_queue
            """
        ).fetchone()
        assert tuple(map(int, daily_totals)) == tuple(map(int, service_totals))

        selected_model = scalar(
            connection,
            """
            SELECT model_name
            FROM analytics.fact_model_evaluation
            WHERE evaluation_scope = 'overall'
              AND backtest_fold = 'ALL'
              AND is_selected_model
            """,
        )
        assert selected_model == "same_weekday_interval_mean_4w"
        assert scalar(
            connection,
            """
            SELECT COUNT(DISTINCT model_name)
            FROM analytics.fact_forecast_interval
            """,
        ) == 4
        assert scalar(
            connection,
            """
            SELECT COUNT(*)
            FROM analytics.fact_staffing_requirement
            WHERE model_name <> 'same_weekday_interval_mean_4w'
            """,
        ) == 0

        view_rows = connection.execute(
            """
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'analytics'
            """
        ).fetchall()
        views = {row[0] for row in view_rows}
        assert EXPECTED_VIEWS <= views

        latest_audit = connection.execute(
            """
            SELECT load_id, loaded_at_utc, table_row_counts
            FROM analytics.mart_load_audit
            ORDER BY load_id DESC
            LIMIT 1
            """
        ).fetchone()
        assert latest_audit is not None
        assert latest_audit[2] == source_counts

        executive_kpis = connection.execute(
            """
            SELECT
                SUM(answered_calls)::numeric / NULLIF(SUM(offered_calls), 0),
                SUM(abandoned_calls)::numeric / NULLIF(SUM(offered_calls), 0),
                SUM(answered_within_20s)::numeric
                    / NULLIF(SUM(service_level_denominator), 0),
                SUM(total_service_seconds_for_aht)::numeric
                    / NULLIF(SUM(aht_eligible_calls), 0)
            FROM analytics.vw_kpi_daily_queue
            """
        ).fetchone()

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": settings.database,
        "status": "passed",
        "source_row_counts": source_counts,
        "database_row_counts": database_counts,
        "total_loaded_rows": sum(database_counts.values()),
        "queue_totals": queue_totals_dict,
        "selected_model": selected_model,
        "views_verified": sorted(EXPECTED_VIEWS),
        "latest_load_id": latest_audit[0],
        "latest_loaded_at_utc": latest_audit[1].isoformat(),
        "executive_kpis": {
            "answer_rate": float(executive_kpis[0]),
            "abandon_rate": float(executive_kpis[1]),
            "service_level_rate": float(executive_kpis[2]),
            "aht_proxy_seconds": float(executive_kpis[3]),
        },
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# PostgreSQL warehouse reconciliation",
        "",
        "Status: **passed**",
        f"Database: `{settings.database}`",
        f"Total loaded rows: **{sum(database_counts.values()):,}**",
        f"Selected model: `{selected_model}`",
        "",
        "## Row counts",
        "",
        "| Table | Source | PostgreSQL |",
        "|---|---:|---:|",
    ]
    for table_name, count in source_counts.items():
        lines.append(f"| `{table_name}` | {count:,} | {database_counts[table_name]:,} |")
    lines.extend(
        [
            "",
            "## Executive KPIs",
            "",
            f"- Answer rate: {float(executive_kpis[0]):.6f}",
            f"- Abandon rate: {float(executive_kpis[1]):.6f}",
            f"- Service level: {float(executive_kpis[2]):.6f}",
            f"- AHT proxy seconds: {float(executive_kpis[3]):.6f}",
            "",
            "All source/database row counts, queue/service totals, model selection, audit metadata and serving views were verified.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    REPORT_SHA.write_text(
        f"{file_sha256(REPORT_JSON)}  {REPORT_JSON.name}\n"
        f"{file_sha256(REPORT_MD)}  {REPORT_MD.name}\n",
        encoding="ascii",
    )
    print("PostgreSQL analytics warehouse validation passed")
    print(f"Loaded rows: {sum(database_counts.values()):,}; views: {len(EXPECTED_VIEWS)}")
    print(
        f"Selected model: {selected_model}; offered={queue_totals_dict['offered_calls']:,}; "
        f"agent_demand={queue_totals_dict['agent_demand_calls']:,}"
    )


if __name__ == "__main__":
    main()
