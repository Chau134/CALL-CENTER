from pathlib import Path

import numpy as np
import pandas as pd

from src.load_analytics_marts import MART_SPECS, normalize_copy_value


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_all_declared_marts_exist_with_unique_columns() -> None:
    assert len(MART_SPECS) == 9
    assert len({spec.table_name for spec in MART_SPECS}) == len(MART_SPECS)
    for spec in MART_SPECS:
        assert spec.path.exists()
        columns = pd.read_csv(spec.path, nrows=0).columns.tolist()
        assert columns
        assert len(columns) == len(set(columns))


def test_copy_value_normalization_handles_pandas_values() -> None:
    assert normalize_copy_value(np.int64(7)) == 7
    assert normalize_copy_value(np.float64(1.5)) == 1.5
    assert normalize_copy_value(np.nan) is None
    assert normalize_copy_value(pd.NA) is None


def test_schema_and_view_sql_cover_all_marts() -> None:
    schema_sql = (PROJECT_ROOT / "sql" / "01_analytics_schema.sql").read_text(
        encoding="utf-8"
    )
    view_sql = (PROJECT_ROOT / "sql" / "02_powerbi_views.sql").read_text(
        encoding="utf-8"
    )
    for spec in MART_SPECS:
        assert f"analytics.{spec.table_name}" in schema_sql
    assert "vw_kpi_daily_queue" in view_sql
    assert "vw_kpi_forecast_weekly_model" in view_sql
    assert "vw_powerbi_staffing_interval" in view_sql
