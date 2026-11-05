import numpy as np
import pandas as pd

from src.run_forecast_staffing import (
    TARGET_METRIC,
    XGBOOST_LAG_MULTIPLIERS,
    build_xgboost_features,
)


def make_feature_frame(rows: int = 2_000) -> pd.DataFrame:
    timestamp = pd.date_range("1999-01-01", periods=rows, freq="30min")
    return pd.DataFrame(
        {
            "local_interval_start": timestamp,
            TARGET_METRIC: np.arange(rows, dtype=float),
            "is_operating_interval": True,
            "is_holiday": False,
            "is_major_holiday": False,
            "is_calendar_day_before_holiday": False,
            "is_calendar_day_after_holiday": False,
            "is_dst_transition_day": False,
        }
    )


def test_xgboost_weekly_lags_reference_expected_history() -> None:
    period = 336
    frame = make_feature_frame()
    features = build_xgboost_features(frame, period)
    target_index = 1_500

    for multiplier in XGBOOST_LAG_MULTIPLIERS:
        lag = period * multiplier
        assert features.loc[target_index, f"lag_{lag}"] == target_index - lag


def test_xgboost_lags_cannot_read_actuals_inside_seven_day_horizon() -> None:
    period = 336
    horizon = 336
    train_end = 1_500
    last_test_index = train_end + horizon - 1
    minimum_lag = period * min(XGBOOST_LAG_MULTIPLIERS)

    assert minimum_lag >= horizon
    assert last_test_index - minimum_lag < train_end
