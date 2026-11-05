"""Validate rolling forecasts, model evaluation, and staffing requirements."""

from __future__ import annotations

import gzip
import json
from collections import Counter

import pandas as pd

try:
    from .run_forecast_staffing import OUTPUT_DIR, REPORT_DIR
    from .staffing import calculate_staffing_requirement
    from .transform_calls import sha256
except ImportError:  # Support direct execution.
    from run_forecast_staffing import OUTPUT_DIR, REPORT_DIR
    from staffing import calculate_staffing_requirement
    from transform_calls import sha256


REPORT_PATH = REPORT_DIR / "forecast_evaluation.json"
BLOCKED_COLUMNS = {"customer_id", "server", "raw_agent_label"}


def read_csv(filename: str) -> pd.DataFrame:
    path = OUTPUT_DIR / filename
    with gzip.open(path, "rt", encoding="utf-8", newline="") as input_file:
        frame = pd.read_csv(input_file, dtype={"target_interval_key": "string"})
    assert not (set(frame.columns) & BLOCKED_COLUMNS)
    return frame


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    selected_model = report["selected_model"]
    forecast = read_csv("fact_forecast_interval.csv.gz")
    evaluation = read_csv("fact_model_evaluation.csv.gz")
    staffing = read_csv("fact_staffing_requirement.csv.gz")

    assert len(forecast) == 3 * 6 * 336
    assert len(evaluation) == 3 * 6 * 3 + 3 * 3
    assert len(staffing) == 336
    assert forecast["forecast_run_id"].nunique() == 18
    assert forecast["model_name"].nunique() == 3
    assert forecast["backtest_fold"].nunique() == 6
    assert forecast["target_metric"].eq("agent_demand_calls").all()
    assert forecast["forecast_agent_demand_calls"].ge(0).all()
    assert forecast["forecast_aht_proxy_seconds"].gt(0).all()
    assert (
        pd.to_datetime(forecast["training_end_date"])
        < pd.to_datetime(forecast["target_local_interval_start"])
    ).all()
    assert (
        pd.to_datetime(forecast["forecast_generated_at"])
        <= pd.to_datetime(forecast["target_local_interval_start"])
    ).all()
    assert (
        forecast["error_actual_minus_forecast"].round(6)
        == (
            forecast["actual_agent_demand_calls"]
            - forecast["forecast_agent_demand_calls"]
        ).round(6)
    ).all()
    for _, run in forecast.groupby("forecast_run_id"):
        assert sorted(run["forecast_horizon_intervals"].tolist()) == list(
            range(1, 337)
        )

    selected_flags = (
        forecast.groupby("model_name")["is_selected_model"].all().to_dict()
    )
    assert selected_flags[selected_model]
    assert sum(bool(value) for value in selected_flags.values()) == 1

    aggregate = evaluation[
        (evaluation["backtest_fold"].astype(str) == "ALL")
        & (evaluation["evaluation_scope"] == "overall")
    ]
    assert len(aggregate) == 3
    selected_row = aggregate.loc[aggregate["model_name"] == selected_model].iloc[0]
    assert selected_row["wape"] == aggregate["wape"].min()
    assert bool(selected_row["is_selected_model"])

    selected_final = forecast[
        (forecast["model_name"] == selected_model)
        & (forecast["backtest_fold"] == 6)
    ].copy()
    assert set(staffing["forecast_run_id"]) == set(selected_final["forecast_run_id"])
    assert staffing["model_name"].eq(selected_model).all()
    assert staffing["actualized_analysis_only"].all()
    for row in staffing.itertuples(index=False):
        expected = calculate_staffing_requirement(
            row.forecast_agent_demand_calls,
            row.forecast_aht_proxy_seconds,
            row.interval_minutes,
            row.occupancy_target,
            row.shrinkage_rate,
        )
        assert abs(row.workload_hours - expected.workload_hours) < 1e-6
        assert row.required_productive_agents == expected.required_productive_agents
        assert row.required_scheduled_agents == expected.required_scheduled_agents

    for filename, metadata in report["outputs"].items():
        assert sha256(OUTPUT_DIR / filename) == metadata["sha256"]

    totals = Counter(
        {
            "forecast_rows": len(forecast),
            "evaluation_rows": len(evaluation),
            "staffing_rows": len(staffing),
        }
    )
    print("Forecast and staffing validation passed")
    print(
        f"Selected={selected_model}; WAPE={selected_row['wape']:.4f}; "
        f"bias={selected_row['bias']:.4f}; MAE={selected_row['mae']:.4f}"
    )
    print(
        f"Rows: forecast={totals['forecast_rows']:,}, "
        f"evaluation={totals['evaluation_rows']:,}, "
        f"staffing={totals['staffing_rows']:,}"
    )


if __name__ == "__main__":
    main()
