-- Read-only checks that must pass before building or refreshing the PBIX model.

-- 1. Dimension key uniqueness and nulls.
SELECT
    'dim_date.date_key' AS check_name,
    COUNT(*) AS row_count,
    COUNT(DISTINCT date_key) AS distinct_key_count,
    COUNT(*) FILTER (WHERE date_key IS NULL) AS null_key_count,
    COUNT(*) = COUNT(DISTINCT date_key)
        AND COUNT(*) FILTER (WHERE date_key IS NULL) = 0 AS passed
FROM analytics.dim_date
UNION ALL
SELECT
    'dim_time_interval.interval_key', COUNT(*), COUNT(DISTINCT interval_key),
    COUNT(*) FILTER (WHERE interval_key IS NULL),
    COUNT(*) = COUNT(DISTINCT interval_key)
        AND COUNT(*) FILTER (WHERE interval_key IS NULL) = 0
FROM analytics.dim_time_interval
UNION ALL
SELECT
    'dim_queue.queue_id', COUNT(*), COUNT(DISTINCT queue_id),
    COUNT(*) FILTER (WHERE queue_id IS NULL),
    COUNT(*) = COUNT(DISTINCT queue_id)
        AND COUNT(*) FILTER (WHERE queue_id IS NULL) = 0
FROM analytics.dim_queue
UNION ALL
SELECT
    'dim_service_type.service_type_code', COUNT(*),
    COUNT(DISTINCT service_type_code),
    COUNT(*) FILTER (WHERE service_type_code IS NULL),
    COUNT(*) = COUNT(DISTINCT service_type_code)
        AND COUNT(*) FILTER (WHERE service_type_code IS NULL) = 0
FROM analytics.dim_service_type;

-- 2. Selected-model target uniqueness. Expected: 2,016 = 6 folds x 336.
SELECT
    COUNT(*) AS selected_rows,
    COUNT(DISTINCT (target_date_key, target_interval_key, queue_id))
        AS distinct_selected_targets,
    COUNT(DISTINCT forecast_run_id) AS selected_runs,
    COUNT(DISTINCT model_name) AS selected_models
FROM analytics.fact_forecast_interval
WHERE is_selected_model;

-- 3. One aggregate evaluation row per model.
SELECT
    COUNT(*) AS aggregate_rows,
    COUNT(DISTINCT model_name) AS aggregate_models,
    COUNT(*) FILTER (WHERE is_selected_model) AS selected_aggregate_rows
FROM analytics.fact_model_evaluation
WHERE backtest_fold = 'ALL'
  AND evaluation_scope = 'overall';

-- 4. Staffing target uniqueness. Expected: 336 rows/targets and one run/model.
SELECT
    COUNT(*) AS staffing_rows,
    COUNT(DISTINCT (target_date_key, target_interval_key, queue_id))
        AS distinct_staffing_targets,
    COUNT(DISTINCT forecast_run_id) AS staffing_runs,
    COUNT(DISTINCT model_name) AS staffing_models,
    COUNT(*) FILTER (WHERE required_scheduled_agents > 0)
        AS intervals_requiring_staff,
    MAX(required_productive_agents) AS peak_productive_agents,
    MAX(required_scheduled_agents) AS peak_scheduled_agents
FROM analytics.fact_staffing_requirement;

-- 5. Queue/service reconciliation.
WITH queue_totals AS (
    SELECT
        SUM(offered_calls) AS offered,
        SUM(agent_demand_calls) AS demand,
        SUM(answered_calls) AS answered,
        SUM(abandoned_calls) AS abandoned
    FROM analytics.fact_queue_interval_complete
),
service_totals AS (
    SELECT
        SUM(offered_calls) AS offered,
        SUM(agent_demand_calls) AS demand,
        SUM(answered_calls) AS answered,
        SUM(abandoned_calls) AS abandoned
    FROM analytics.fact_service_type_interval
)
SELECT
    q.offered AS queue_offered,
    s.offered AS service_offered,
    q.demand AS queue_demand,
    s.demand AS service_demand,
    q.answered AS queue_answered,
    s.answered AS service_answered,
    q.abandoned AS queue_abandoned,
    s.abandoned AS service_abandoned,
    q = s AS passed
FROM queue_totals AS q
CROSS JOIN service_totals AS s;

-- 6. Power BI KPI benchmarks.
SELECT
    SUM(offered_calls) AS offered_calls,
    SUM(agent_demand_calls) AS agent_demand_calls,
    SUM(answered_calls)::numeric / NULLIF(SUM(offered_calls), 0) AS answer_rate,
    SUM(abandoned_calls)::numeric / NULLIF(SUM(offered_calls), 0) AS abandon_rate,
    SUM(answered_within_20s)::numeric
        / NULLIF(SUM(service_level_denominator), 0) AS service_level,
    SUM(total_service_seconds_for_aht)::numeric
        / NULLIF(SUM(aht_eligible_calls), 0) AS aht_proxy_seconds
FROM analytics.fact_queue_interval_complete;
