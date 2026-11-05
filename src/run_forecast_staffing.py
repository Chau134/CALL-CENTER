"""Run rolling-origin forecasts and workload-based staffing calculations."""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import yaml
from statsmodels.tsa.holtwinters import ExponentialSmoothing

try:
    from .staffing import calculate_staffing_requirement
    from .transform_calls import PROJECT_ROOT, sha256
except ImportError:  # Support direct execution.
    from staffing import calculate_staffing_requirement
    from transform_calls import PROJECT_ROOT, sha256


INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "technion"
    / "fact_queue_interval_complete.csv.gz"
)
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "technion"
REPORT_DIR = PROJECT_ROOT / "reports" / "model_evaluation"
CONFIG_PATH = PROJECT_ROOT / "config" / "project.yml"
MODEL_VERSION = "1.0.0"
TARGET_METRIC = "agent_demand_calls"


FORECAST_COLUMNS = [
    "forecast_run_id",
    "forecast_generated_at",
    "artifact_generated_at_utc",
    "target_local_interval_start",
    "target_date_key",
    "target_interval_key",
    "queue_id",
    "target_metric",
    "model_name",
    "model_version",
    "training_start_date",
    "training_end_date",
    "forecast_agent_demand_calls",
    "actual_agent_demand_calls",
    "forecast_aht_proxy_seconds",
    "actual_aht_proxy_seconds",
    "error_actual_minus_forecast",
    "absolute_error",
    "squared_error",
    "percentage_error",
    "backtest_fold",
    "forecast_horizon_intervals",
    "forecast_type",
    "forecast_quantile",
    "evaluation_status",
    "is_selected_model",
    "is_operating_interval",
    "data_origin",
    "source_fact",
    "etl_run_id",
]

EVALUATION_COLUMNS = [
    "model_name",
    "model_version",
    "forecast_type",
    "evaluation_scope",
    "backtest_fold",
    "training_start_date",
    "training_end_date",
    "test_start",
    "test_end",
    "evaluated_intervals",
    "actual_sum",
    "forecast_sum",
    "mae",
    "rmse",
    "wape",
    "bias",
    "is_selected_model",
    "data_origin",
]

STAFFING_COLUMNS = [
    "target_local_interval_start",
    "target_date_key",
    "target_interval_key",
    "queue_id",
    "forecast_run_id",
    "model_name",
    "target_metric",
    "forecast_agent_demand_calls",
    "forecast_aht_proxy_seconds",
    "workload_hours",
    "interval_minutes",
    "occupancy_target",
    "shrinkage_rate",
    "required_productive_agents",
    "required_scheduled_agents",
    "staffing_method",
    "assumption_version",
    "actual_agent_demand_calls",
    "actual_aht_proxy_seconds",
    "actualized_workload_hours",
    "actualized_productive_agents",
    "actualized_scheduled_agents",
    "actualized_analysis_only",
    "is_operating_interval",
    "data_origin",
]


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def load_series() -> pd.DataFrame:
    frame = pd.read_csv(INPUT_PATH)
    frame = frame.sort_values(["date_key", "interval_key"]).reset_index(drop=True)
    if len(frame) != 17_520:
        raise RuntimeError(f"Expected 17,520 intervals, got {len(frame):,}")
    if frame.duplicated(["date_key", "interval_key", "queue_id"]).any():
        raise RuntimeError("Duplicate interval grain in foundation mart")
    if int(frame[TARGET_METRIC].sum()) != 417_149:
        raise RuntimeError("Agent-demand total changed; rebuild and review foundation mart")
    frame["local_interval_start"] = pd.to_datetime(frame["local_interval_start"])
    frame["aht_proxy_seconds"] = pd.to_numeric(
        frame["aht_proxy_seconds"], errors="coerce"
    )
    return frame


def seasonal_naive(train: np.ndarray, horizon: int, period: int) -> np.ndarray:
    if len(train) < period:
        raise ValueError("Training data shorter than seasonal period")
    pattern = train[-period:]
    return np.resize(pattern, horizon).astype(float)


def same_weekday_interval_mean(
    train: np.ndarray, horizon: int, period: int, weeks: int = 4
) -> np.ndarray:
    required = period * weeks
    if len(train) < required:
        raise ValueError("Training data shorter than requested history")
    history = np.stack(
        [train[-period * lag : -period * (lag - 1) if lag > 1 else None] for lag in range(1, weeks + 1)]
    )
    pattern = history.mean(axis=0)
    return np.resize(pattern, horizon).astype(float)


def holt_winters(train: np.ndarray, horizon: int, period: int) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = ExponentialSmoothing(
            train.astype(float),
            trend="add",
            damped_trend=True,
            seasonal="add",
            seasonal_periods=period,
            initialization_method="estimated",
        )
        fitted = model.fit(optimized=True, use_brute=False, remove_bias=False)
    return np.asarray(fitted.forecast(horizon), dtype=float)


def forecast_aht_proxy(
    frame: pd.DataFrame, train_end: int, test_start: int, horizon: int, period: int
) -> tuple[np.ndarray, float, float]:
    train = frame.iloc[:train_end]
    eligible = train[train["aht_eligible_calls"] > 0]
    if eligible.empty:
        raise RuntimeError("No AHT-eligible history")
    recent = train.tail(28 * 48)
    recent_denominator = int(recent["aht_eligible_calls"].sum())
    if recent_denominator:
        fallback = float(
            recent["total_service_seconds_for_aht"].sum() / recent_denominator
        )
    else:
        fallback = float(
            eligible["total_service_seconds_for_aht"].sum()
            / eligible["aht_eligible_calls"].sum()
        )
    lower = float(eligible["aht_proxy_seconds"].quantile(0.05))
    upper = float(eligible["aht_proxy_seconds"].quantile(0.95))
    predictions: list[float] = []
    for target_index in range(test_start, test_start + horizon):
        lag_indices = [target_index - period * lag for lag in range(1, 5)]
        lag_indices = [index for index in lag_indices if 0 <= index < train_end]
        lag_rows = frame.iloc[lag_indices]
        denominator = int(lag_rows["aht_eligible_calls"].sum())
        if denominator:
            value = float(
                lag_rows["total_service_seconds_for_aht"].sum() / denominator
            )
        else:
            value = fallback
        predictions.append(float(np.clip(value, lower, upper)))
    return np.asarray(predictions), lower, upper


def metrics(actual: np.ndarray, forecast: np.ndarray) -> dict[str, float | None]:
    error = actual - forecast
    actual_sum = float(actual.sum())
    return {
        "actual_sum": round(actual_sum, 6),
        "forecast_sum": round(float(forecast.sum()), 6),
        "mae": round(float(np.mean(np.abs(error))), 6),
        "rmse": round(float(np.sqrt(np.mean(np.square(error)))), 6),
        "wape": (
            round(float(np.abs(error).sum() / actual_sum), 6)
            if actual_sum
            else None
        ),
        "bias": (
            round(float((forecast.sum() - actual_sum) / actual_sum), 6)
            if actual_sum
            else None
        ),
    }


def model_registry() -> dict[str, tuple[str, Callable[[np.ndarray, int, int], np.ndarray]]]:
    return {
        "seasonal_naive_7d": ("baseline", seasonal_naive),
        "same_weekday_interval_mean_4w": (
            "baseline",
            lambda train, horizon, period: same_weekday_interval_mean(
                train, horizon, period, weeks=4
            ),
        ),
        "holt_winters_additive_damped": ("candidate", holt_winters),
    }


def aggregate_evaluations(fold_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregate_rows: list[dict[str, Any]] = []
    groups = sorted(
        {(row["model_name"], row["evaluation_scope"]) for row in fold_rows}
    )
    for model_name, evaluation_scope in groups:
        selected = [
            row
            for row in fold_rows
            if row["model_name"] == model_name
            and row["evaluation_scope"] == evaluation_scope
        ]
        actual_sum = sum(row["actual_sum"] for row in selected)
        absolute_error_sum = sum(row["absolute_error_sum"] for row in selected)
        squared_error_sum = sum(row["squared_error_sum"] for row in selected)
        signed_forecast_minus_actual = sum(
            row["forecast_sum"] - row["actual_sum"] for row in selected
        )
        intervals = sum(row["evaluated_intervals"] for row in selected)
        aggregate_rows.append(
            {
                "model_name": model_name,
                "model_version": MODEL_VERSION,
                "forecast_type": selected[0]["forecast_type"],
                "evaluation_scope": evaluation_scope,
                "backtest_fold": "ALL",
                "training_start_date": min(
                    row["training_start_date"] for row in selected
                ),
                "training_end_date": max(row["training_end_date"] for row in selected),
                "test_start": min(row["test_start"] for row in selected),
                "test_end": max(row["test_end"] for row in selected),
                "evaluated_intervals": intervals,
                "actual_sum": round(actual_sum, 6),
                "forecast_sum": round(
                    sum(row["forecast_sum"] for row in selected), 6
                ),
                "mae": round(absolute_error_sum / intervals, 6),
                "rmse": round(math.sqrt(squared_error_sum / intervals), 6),
                "wape": (
                    round(absolute_error_sum / actual_sum, 6)
                    if actual_sum
                    else None
                ),
                "bias": (
                    round(signed_forecast_minus_actual / actual_sum, 6)
                    if actual_sum
                    else None
                ),
                "is_selected_model": False,
                "data_origin": "derived",
            }
        )
    return aggregate_rows


def run_backtest(
    frame: pd.DataFrame, config: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, dict[str, Any]]:
    forecast_config = config["forecast"]
    period = int(forecast_config["weekly_seasonality_intervals"])
    horizon = int(forecast_config["horizon_days"] * 48)
    folds = int(forecast_config["backtest_folds"])
    step = int(forecast_config["backtest_step_days"] * 48)
    if step != horizon:
        raise ValueError("Current implementation requires backtest step = horizon")
    first_test_start = len(frame) - folds * horizon
    if first_test_start < forecast_config["minimum_training_days"] * 48:
        raise RuntimeError("Not enough history for configured backtest")

    target = frame[TARGET_METRIC].to_numpy(dtype=float)
    generated_at = datetime.now(timezone.utc).isoformat()
    forecast_records: list[dict[str, Any]] = []
    evaluation_rows: list[dict[str, Any]] = []
    aht_bounds: list[tuple[float, float]] = []

    for fold in range(1, folds + 1):
        test_start = first_test_start + (fold - 1) * step
        train_end = test_start
        test_end = test_start + horizon
        train = target[:train_end]
        actual = target[test_start:test_end]
        aht_forecast, aht_lower, aht_upper = forecast_aht_proxy(
            frame, train_end, test_start, horizon, period
        )
        aht_bounds.append((aht_lower, aht_upper))

        for model_name, (forecast_type, model_function) in model_registry().items():
            prediction = np.clip(model_function(train, horizon, period), 0, None)
            error = actual - prediction
            operating_mask = frame.iloc[test_start:test_end][
                "is_operating_interval"
            ].to_numpy(dtype=bool)
            scope_masks = {
                "overall": np.ones(horizon, dtype=bool),
                "operating": operating_mask,
                "closed": ~operating_mask,
            }
            for evaluation_scope, mask in scope_masks.items():
                scoped_actual = actual[mask]
                scoped_prediction = prediction[mask]
                scoped_error = scoped_actual - scoped_prediction
                fold_metrics = metrics(scoped_actual, scoped_prediction)
                evaluation_rows.append(
                    {
                        "model_name": model_name,
                        "model_version": MODEL_VERSION,
                        "forecast_type": forecast_type,
                        "evaluation_scope": evaluation_scope,
                        "backtest_fold": fold,
                        "training_start_date": frame.iloc[0][
                            "local_interval_start"
                        ].date().isoformat(),
                        "training_end_date": frame.iloc[train_end - 1][
                            "local_interval_start"
                        ].isoformat(),
                        "test_start": frame.iloc[test_start][
                            "local_interval_start"
                        ].isoformat(),
                        "test_end": frame.iloc[test_end - 1][
                            "local_interval_start"
                        ].isoformat(),
                        "evaluated_intervals": int(mask.sum()),
                        **fold_metrics,
                        "absolute_error_sum": float(np.abs(scoped_error).sum()),
                        "squared_error_sum": float(np.square(scoped_error).sum()),
                        "is_selected_model": False,
                        "data_origin": "derived",
                    }
                )
            run_id = f"bt1999_f{fold:02d}_{model_name}_v1"
            for offset in range(horizon):
                source_row = frame.iloc[test_start + offset]
                actual_value = float(actual[offset])
                forecast_value = float(prediction[offset])
                signed_error = actual_value - forecast_value
                actual_aht = source_row["aht_proxy_seconds"]
                forecast_records.append(
                    {
                        "forecast_run_id": run_id,
                        "forecast_generated_at": frame.iloc[train_end][
                            "local_interval_start"
                        ].isoformat(),
                        "artifact_generated_at_utc": generated_at,
                        "target_local_interval_start": source_row[
                            "local_interval_start"
                        ].isoformat(),
                        "target_date_key": int(source_row["date_key"]),
                        "target_interval_key": f"{int(source_row['interval_key']):04d}",
                        "queue_id": source_row["queue_id"],
                        "target_metric": TARGET_METRIC,
                        "model_name": model_name,
                        "model_version": MODEL_VERSION,
                        "training_start_date": frame.iloc[0][
                            "local_interval_start"
                        ].date().isoformat(),
                        "training_end_date": frame.iloc[train_end - 1][
                            "local_interval_start"
                        ].isoformat(),
                        "forecast_agent_demand_calls": round(forecast_value, 6),
                        "actual_agent_demand_calls": int(actual_value),
                        "forecast_aht_proxy_seconds": round(
                            float(aht_forecast[offset]), 6
                        ),
                        "actual_aht_proxy_seconds": (
                            "" if pd.isna(actual_aht) else round(float(actual_aht), 6)
                        ),
                        "error_actual_minus_forecast": round(signed_error, 6),
                        "absolute_error": round(abs(signed_error), 6),
                        "squared_error": round(signed_error**2, 6),
                        "percentage_error": (
                            round(signed_error / actual_value, 6)
                            if actual_value
                            else ""
                        ),
                        "backtest_fold": fold,
                        "forecast_horizon_intervals": offset + 1,
                        "forecast_type": forecast_type,
                        "forecast_quantile": "",
                        "evaluation_status": "evaluated",
                        "is_selected_model": False,
                        "is_operating_interval": bool(
                            source_row["is_operating_interval"]
                        ),
                        "data_origin": "derived",
                        "source_fact": "fact_queue_interval_complete",
                        "etl_run_id": source_row["etl_run_id"],
                    }
                )

    aggregate_rows = aggregate_evaluations(evaluation_rows)
    selected_row = min(
        [row for row in aggregate_rows if row["evaluation_scope"] == "overall"],
        key=lambda row: (row["wape"], abs(row["bias"]), row["mae"]),
    )
    selected_model = selected_row["model_name"]
    for row in forecast_records:
        row["is_selected_model"] = row["model_name"] == selected_model
    for row in evaluation_rows + aggregate_rows:
        row["is_selected_model"] = row["model_name"] == selected_model

    aht_metadata = {
        "method": "weighted same-weekday interval mean over previous 4 weeks; fallback to trailing 28-day weighted AHT proxy",
        "lower_clip_min_across_folds": round(min(item[0] for item in aht_bounds), 6),
        "upper_clip_max_across_folds": round(max(item[1] for item in aht_bounds), 6),
    }
    return forecast_records, evaluation_rows + aggregate_rows, selected_model, aht_metadata


def build_staffing(
    forecast_records: list[dict[str, Any]],
    selected_model: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    final_fold = int(config["forecast"]["backtest_folds"])
    interval_minutes = int(config["scope"]["interval_minutes"])
    occupancy = float(config["workforce"]["occupancy_target"])
    shrinkage = float(config["workforce"]["shrinkage_rate"])
    rows: list[dict[str, Any]] = []
    for forecast in forecast_records:
        if (
            forecast["model_name"] != selected_model
            or forecast["backtest_fold"] != final_fold
        ):
            continue
        planned = calculate_staffing_requirement(
            float(forecast["forecast_agent_demand_calls"]),
            float(forecast["forecast_aht_proxy_seconds"]),
            interval_minutes,
            occupancy,
            shrinkage,
        )
        actual_aht = forecast["actual_aht_proxy_seconds"]
        actualized = None
        if actual_aht != "":
            actualized = calculate_staffing_requirement(
                float(forecast["actual_agent_demand_calls"]),
                float(actual_aht),
                interval_minutes,
                occupancy,
                shrinkage,
            )
        rows.append(
            {
                "target_local_interval_start": forecast[
                    "target_local_interval_start"
                ],
                "target_date_key": forecast["target_date_key"],
                "target_interval_key": forecast["target_interval_key"],
                "queue_id": forecast["queue_id"],
                "forecast_run_id": forecast["forecast_run_id"],
                "model_name": selected_model,
                "target_metric": TARGET_METRIC,
                "forecast_agent_demand_calls": forecast[
                    "forecast_agent_demand_calls"
                ],
                "forecast_aht_proxy_seconds": forecast[
                    "forecast_aht_proxy_seconds"
                ],
                "workload_hours": planned.workload_hours,
                "interval_minutes": interval_minutes,
                "occupancy_target": occupancy,
                "shrinkage_rate": shrinkage,
                "required_productive_agents": planned.required_productive_agents,
                "required_scheduled_agents": planned.required_scheduled_agents,
                "staffing_method": "capacity_workload_baseline",
                "assumption_version": "project_yml_v1",
                "actual_agent_demand_calls": forecast[
                    "actual_agent_demand_calls"
                ],
                "actual_aht_proxy_seconds": actual_aht,
                "actualized_workload_hours": (
                    "" if actualized is None else actualized.workload_hours
                ),
                "actualized_productive_agents": (
                    "" if actualized is None else actualized.required_productive_agents
                ),
                "actualized_scheduled_agents": (
                    "" if actualized is None else actualized.required_scheduled_agents
                ),
                "actualized_analysis_only": True,
                "is_operating_interval": forecast["is_operating_interval"],
                "data_origin": "derived",
            }
        )
    if len(rows) != 336:
        raise RuntimeError(f"Expected 336 staffing rows, got {len(rows)}")
    return rows


def write_gzip_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    frame = pd.DataFrame(rows)
    missing = set(columns) - set(frame.columns)
    if missing:
        raise RuntimeError(f"Missing output columns for {path.name}: {sorted(missing)}")
    with gzip.open(path, "wt", encoding="utf-8", newline="") as output_file:
        frame[columns].to_csv(output_file, index=False)


def write_reports(
    evaluation_rows: list[dict[str, Any]],
    selected_model: str,
    aht_metadata: dict[str, Any],
    output_paths: list[Path],
) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    aggregate = [row for row in evaluation_rows if row["backtest_fold"] == "ALL"]
    overall_aggregate = [
        row for row in aggregate if row["evaluation_scope"] == "overall"
    ]
    report = {
        "report_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_metric": TARGET_METRIC,
        "selected_model": selected_model,
        "selection_rule": "minimum aggregate WAPE, then absolute bias, then MAE",
        "backtest": {
            "method": "rolling_origin",
            "folds": 6,
            "horizon_intervals": 336,
            "random_split_used": False,
        },
        "aggregate_metrics": aggregate,
        "aht_forecast": aht_metadata,
        "staffing": {
            "method": "capacity_workload_baseline",
            "is_erlang_c": False,
            "actualized_columns_are_retrospective_only": True,
        },
        "outputs": {
            path.name: {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in output_paths
        },
    }
    json_path = REPORT_DIR / "forecast_evaluation.json"
    md_path = REPORT_DIR / "forecast_evaluation.md"
    checksum_path = REPORT_DIR / "forecast_evaluation.sha256"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Forecast evaluation",
        "",
        f"Target: `{TARGET_METRIC}`",
        f"Selected model: **{selected_model}**",
        "",
        "## Aggregate rolling-origin metrics",
        "",
        "| Model | Type | WAPE | Bias | MAE | RMSE |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in sorted(overall_aggregate, key=lambda item: item["wape"]):
        lines.append(
            f"| {row['model_name']} | {row['forecast_type']} | "
            f"{row['wape']:.4f} | {row['bias']:.4f} | "
            f"{row['mae']:.4f} | {row['rmse']:.4f} |"
        )
    lines.extend(
        [
            "",
            "Six 7-day rolling folds were evaluated without random split.",
            "Staffing uses forecast agent-demand and forecast AHT proxy.",
            "Actualized staffing columns are retrospective analysis only.",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    checksum_path.write_text(
        f"{sha256(json_path)}  {json_path.name}\n"
        f"{sha256(md_path)}  {md_path.name}\n",
        encoding="ascii",
    )


def main() -> None:
    config = load_config()
    frame = load_series()
    forecasts, evaluations, selected_model, aht_metadata = run_backtest(
        frame, config
    )
    staffing = build_staffing(forecasts, selected_model, config)
    forecast_path = OUTPUT_DIR / "fact_forecast_interval.csv.gz"
    evaluation_path = OUTPUT_DIR / "fact_model_evaluation.csv.gz"
    staffing_path = OUTPUT_DIR / "fact_staffing_requirement.csv.gz"
    write_gzip_csv(forecast_path, forecasts, FORECAST_COLUMNS)
    public_evaluations = [
        {key: value for key, value in row.items() if key in EVALUATION_COLUMNS}
        for row in evaluations
    ]
    write_gzip_csv(evaluation_path, public_evaluations, EVALUATION_COLUMNS)
    write_gzip_csv(staffing_path, staffing, STAFFING_COLUMNS)
    write_reports(
        public_evaluations,
        selected_model,
        aht_metadata,
        [forecast_path, evaluation_path, staffing_path],
    )
    selected = next(
        row
        for row in public_evaluations
        if row["backtest_fold"] == "ALL"
        and row["evaluation_scope"] == "overall"
        and row["model_name"] == selected_model
    )
    print(f"Selected model: {selected_model}")
    print(
        f"Aggregate WAPE={selected['wape']:.4f}, bias={selected['bias']:.4f}, "
        f"MAE={selected['mae']:.4f}"
    )
    print(
        f"Outputs: forecast={len(forecasts):,}, evaluation={len(evaluations):,}, "
        f"staffing={len(staffing):,} rows"
    )


if __name__ == "__main__":
    main()
