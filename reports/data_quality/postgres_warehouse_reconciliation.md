# PostgreSQL warehouse reconciliation

Status: **passed**
Database: `call_center_wfm`
Total loaded rows: **131,544**
Selected model: `same_weekday_interval_mean_4w`

## Row counts

| Table | Source | PostgreSQL |
|---|---:|---:|
| `dim_date` | 365 | 365 |
| `dim_time_interval` | 48 | 48 |
| `dim_queue` | 1 | 1 |
| `dim_service_type` | 6 | 6 |
| `fact_queue_interval_complete` | 17,520 | 17,520 |
| `fact_service_type_interval` | 105,120 | 105,120 |
| `fact_forecast_interval` | 8,064 | 8,064 |
| `fact_model_evaluation` | 84 | 84 |
| `fact_staffing_requirement` | 336 | 336 |

## Executive KPIs

- Answer rate: 0.801061
- Abandon rate: 0.198939
- Service level: 0.464631
- AHT proxy seconds: 194.251921

All source/database row counts, queue/service totals, model selection, audit metadata and serving views were verified.
