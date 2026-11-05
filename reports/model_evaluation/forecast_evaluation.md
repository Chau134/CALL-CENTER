# Forecast evaluation

Target: `agent_demand_calls`
Selected model: **same_weekday_interval_mean_4w**

## Aggregate rolling-origin metrics

| Model | Type | WAPE | Bias | MAE | RMSE |
|---|---|---:|---:|---:|---:|
| same_weekday_interval_mean_4w | baseline | 0.1795 | -0.0121 | 4.7801 | 8.0246 |
| xgboost_lag_calendar | candidate | 0.1861 | 0.0108 | 4.9540 | 8.0561 |
| seasonal_naive_7d | baseline | 0.2297 | -0.0045 | 6.1161 | 10.2972 |
| holt_winters_additive_damped | candidate | 0.2781 | -0.2079 | 7.4048 | 11.9786 |

Six 7-day rolling folds were evaluated without random split.
Staffing uses forecast agent-demand and forecast AHT proxy.
Actualized staffing columns are retrospective analysis only.
