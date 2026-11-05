# Power BI model readiness

Status: **passed**
Database: `call_center_wfm`

## Checks

- [x] `dim_date_key_unique`
- [x] `dim_time_interval_key_unique`
- [x] `dim_queue_key_unique`
- [x] `dim_service_type_key_unique`
- [x] `selected_forecast_targets_unique`
- [x] `one_aggregate_evaluation_per_model`
- [x] `staffing_targets_unique`
- [x] `service_type_reconciles_to_queue`
- [x] `queue_benchmarks_match`
- [x] `executive_kpis_available`
- [x] `refresh_metadata_available`
- [x] `refresh_rows_available`

## Verified grains

- Selected forecast: 2,016 rows / 2,016 unique targets / 6 runs.
- Staffing: 336 rows / 336 unique targets / 1 run.
- Aggregate evaluation: 4 rows / 4 models / 1 selected row.
- Service-type totals reconcile to queue totals: 440,844 offered calls.
