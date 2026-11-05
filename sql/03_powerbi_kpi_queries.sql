-- Example SQL queries for Power BI validation and portfolio analysis.
-- These are read-only examples; serving views are defined in 02_powerbi_views.sql.

-- 1. Executive KPI cards for the complete observed period.
SELECT
    SUM(offered_calls) AS offered_calls,
    SUM(answered_calls)::numeric / NULLIF(SUM(offered_calls), 0) AS answer_rate,
    SUM(abandoned_calls)::numeric / NULLIF(SUM(offered_calls), 0) AS abandon_rate,
    SUM(answered_within_20s)::numeric
        / NULLIF(SUM(service_level_denominator), 0) AS service_level_rate,
    SUM(total_service_seconds_for_aht)::numeric
        / NULLIF(SUM(aht_eligible_calls), 0) AS aht_proxy_seconds
FROM analytics.vw_kpi_daily_queue;

-- 2. Peak intervals by day using a window function.
WITH ranked AS (
    SELECT
        calendar_date,
        start_time,
        queue_id,
        offered_calls,
        agent_demand_calls,
        dense_rank() OVER (
            PARTITION BY calendar_date, queue_id
            ORDER BY agent_demand_calls DESC
        ) AS demand_rank
    FROM analytics.vw_powerbi_queue_interval
)
SELECT *
FROM ranked
WHERE demand_rank <= 3
ORDER BY calendar_date, queue_id, demand_rank, start_time;

-- 3. Weekly forecast accuracy by model.
SELECT
    target_week_start_date,
    model_name,
    backtest_fold,
    evaluated_intervals,
    actual_calls,
    forecast_calls,
    wape,
    bias,
    mae,
    rmse,
    is_selected_model
FROM analytics.vw_kpi_forecast_weekly_model
ORDER BY target_week_start_date, wape;

-- 4. Selected-model planned staffing requirement by date.
SELECT
    calendar_date,
    model_name,
    planned_workload_hours,
    peak_required_productive_agents,
    peak_required_scheduled_agents,
    required_productive_agent_hours,
    required_scheduled_agent_hours
FROM analytics.vw_kpi_staffing_daily
ORDER BY calendar_date;

-- 5. Rolling 7/28-day offered calls and AHT proxy.
SELECT
    calendar_date,
    queue_id,
    offered_calls,
    SUM(offered_calls) OVER (
        PARTITION BY queue_id ORDER BY calendar_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS offered_calls_rolling_7d,
    SUM(offered_calls) OVER (
        PARTITION BY queue_id ORDER BY calendar_date
        ROWS BETWEEN 27 PRECEDING AND CURRENT ROW
    ) AS offered_calls_rolling_28d,
    SUM(total_service_seconds_for_aht) OVER (
        PARTITION BY queue_id ORDER BY calendar_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    )::numeric
    / NULLIF(
        SUM(aht_eligible_calls) OVER (
            PARTITION BY queue_id ORDER BY calendar_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ), 0
    ) AS aht_proxy_rolling_7d
FROM analytics.vw_kpi_daily_queue
ORDER BY calendar_date, queue_id;

-- Staffing gap, attendance, adherence, occupancy and agent/team ranking are
-- intentionally omitted until schedule/attendance/state marts exist.
