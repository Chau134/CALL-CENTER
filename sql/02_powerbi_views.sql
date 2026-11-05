-- KPI and serving views for Power BI.
-- Ratios are always recalculated from additive numerators/denominators.

CREATE OR REPLACE VIEW analytics.vw_powerbi_queue_interval AS
SELECT
    f.date_key,
    d.calendar_date,
    d.week_start_date,
    d.year_number,
    d.quarter_number,
    d.month_number,
    d.month_name,
    d.week_of_year,
    d.day_of_week_iso,
    d.day_name,
    d.is_weekend,
    d.is_holiday,
    d.holiday_name,
    f.interval_key,
    ti.interval_number,
    ti.start_time,
    ti.end_time,
    ti.hour_number,
    ti.minute_number,
    ti.daypart,
    f.queue_id,
    q.queue_name,
    f.local_interval_start,
    f.local_interval_end,
    f.is_operating_interval,
    f.coverage_status,
    f.has_calls,
    f.offered_calls,
    f.agent_demand_calls,
    f.answered_calls,
    f.abandoned_calls,
    f.queue_abandoned_calls,
    f.vru_abandoned_calls,
    f.short_abandon_calls,
    f.answered_within_20s,
    f.service_level_denominator,
    f.total_wait_seconds,
    f.aht_eligible_calls,
    f.total_service_seconds_for_aht,
    f.answered_calls::numeric / NULLIF(f.offered_calls, 0) AS answer_rate,
    f.abandoned_calls::numeric / NULLIF(f.offered_calls, 0) AS abandon_rate,
    f.short_abandon_calls::numeric / NULLIF(f.offered_calls, 0) AS short_abandon_rate,
    f.agent_demand_calls::numeric / NULLIF(f.offered_calls, 0) AS queue_reach_rate,
    f.answered_within_20s::numeric
        / NULLIF(f.service_level_denominator, 0) AS service_level_rate,
    f.total_wait_seconds::numeric / NULLIF(f.offered_calls, 0)
        AS avg_wait_seconds_all_calls,
    f.total_service_seconds_for_aht::numeric / NULLIF(f.aht_eligible_calls, 0)
        AS aht_proxy_seconds,
    f.data_origin,
    f.etl_run_id
FROM analytics.fact_queue_interval_complete AS f
JOIN analytics.dim_date AS d ON d.date_key = f.date_key
JOIN analytics.dim_time_interval AS ti ON ti.interval_key = f.interval_key
JOIN analytics.dim_queue AS q ON q.queue_id = f.queue_id;

CREATE OR REPLACE VIEW analytics.vw_kpi_daily_queue AS
SELECT
    f.date_key,
    d.calendar_date,
    d.week_start_date,
    d.year_number,
    d.quarter_number,
    d.month_number,
    d.month_name,
    d.week_of_year,
    d.day_of_week_iso,
    d.day_name,
    d.is_weekend,
    d.is_holiday,
    d.holiday_name,
    f.queue_id,
    q.queue_name,
    SUM(f.offered_calls) AS offered_calls,
    SUM(f.agent_demand_calls) AS agent_demand_calls,
    SUM(f.answered_calls) AS answered_calls,
    SUM(f.abandoned_calls) AS abandoned_calls,
    SUM(f.queue_abandoned_calls) AS queue_abandoned_calls,
    SUM(f.vru_abandoned_calls) AS vru_abandoned_calls,
    SUM(f.short_abandon_calls) AS short_abandon_calls,
    SUM(f.answered_within_20s) AS answered_within_20s,
    SUM(f.service_level_denominator) AS service_level_denominator,
    SUM(f.total_wait_seconds) AS total_wait_seconds,
    SUM(f.aht_eligible_calls) AS aht_eligible_calls,
    SUM(f.total_service_seconds_for_aht) AS total_service_seconds_for_aht,
    SUM(f.answered_calls)::numeric / NULLIF(SUM(f.offered_calls), 0)
        AS answer_rate,
    SUM(f.abandoned_calls)::numeric / NULLIF(SUM(f.offered_calls), 0)
        AS abandon_rate,
    SUM(f.short_abandon_calls)::numeric / NULLIF(SUM(f.offered_calls), 0)
        AS short_abandon_rate,
    SUM(f.answered_within_20s)::numeric
        / NULLIF(SUM(f.service_level_denominator), 0) AS service_level_rate,
    SUM(f.total_wait_seconds)::numeric / NULLIF(SUM(f.offered_calls), 0)
        AS avg_wait_seconds_all_calls,
    SUM(f.total_service_seconds_for_aht)::numeric
        / NULLIF(SUM(f.aht_eligible_calls), 0) AS aht_proxy_seconds,
    COUNT(*) FILTER (WHERE f.is_operating_interval) AS operating_intervals,
    COUNT(*) FILTER (WHERE f.has_calls) AS intervals_with_calls
FROM analytics.fact_queue_interval_complete AS f
JOIN analytics.dim_date AS d ON d.date_key = f.date_key
JOIN analytics.dim_queue AS q ON q.queue_id = f.queue_id
GROUP BY
    f.date_key, d.calendar_date, d.week_start_date, d.year_number,
    d.quarter_number, d.month_number, d.month_name, d.week_of_year,
    d.day_of_week_iso, d.day_name, d.is_weekend, d.is_holiday,
    d.holiday_name, f.queue_id, q.queue_name;

CREATE OR REPLACE VIEW analytics.vw_kpi_service_type_daily AS
SELECT
    f.date_key,
    d.calendar_date,
    d.week_start_date,
    d.day_of_week_iso,
    d.day_name,
    f.queue_id,
    f.service_type_code,
    st.service_type_name,
    SUM(f.offered_calls) AS offered_calls,
    SUM(f.agent_demand_calls) AS agent_demand_calls,
    SUM(f.answered_calls) AS answered_calls,
    SUM(f.abandoned_calls) AS abandoned_calls,
    SUM(f.short_abandon_calls) AS short_abandon_calls,
    SUM(f.answered_within_20s) AS answered_within_20s,
    SUM(f.valid_for_aht_calls) AS aht_eligible_calls,
    SUM(f.service_seconds_sum_for_aht) AS total_service_seconds_for_aht,
    SUM(f.answered_calls)::numeric / NULLIF(SUM(f.offered_calls), 0)
        AS answer_rate,
    SUM(f.abandoned_calls)::numeric / NULLIF(SUM(f.offered_calls), 0)
        AS abandon_rate,
    SUM(f.service_seconds_sum_for_aht)::numeric
        / NULLIF(SUM(f.valid_for_aht_calls), 0) AS aht_proxy_seconds
FROM analytics.fact_service_type_interval AS f
JOIN analytics.dim_date AS d ON d.date_key = f.date_key
JOIN analytics.dim_service_type AS st
    ON st.service_type_code = f.service_type_code
   AND st.queue_id = f.queue_id
GROUP BY
    f.date_key, d.calendar_date, d.week_start_date, d.day_of_week_iso,
    d.day_name, f.queue_id, f.service_type_code, st.service_type_name;

CREATE OR REPLACE VIEW analytics.vw_powerbi_forecast_interval AS
SELECT
    f.forecast_run_id,
    f.forecast_generated_at,
    f.artifact_generated_at_utc,
    f.target_local_interval_start,
    f.target_date_key,
    d.calendar_date AS target_calendar_date,
    d.week_start_date AS target_week_start_date,
    d.day_of_week_iso,
    d.day_name,
    d.is_holiday,
    f.target_interval_key,
    ti.interval_number,
    ti.start_time,
    ti.daypart,
    f.queue_id,
    q.queue_name,
    f.model_name,
    f.model_version,
    f.forecast_type,
    f.backtest_fold,
    f.forecast_horizon_intervals,
    f.is_selected_model,
    f.is_operating_interval,
    f.forecast_agent_demand_calls,
    f.actual_agent_demand_calls,
    f.forecast_aht_proxy_seconds,
    f.actual_aht_proxy_seconds,
    f.error_actual_minus_forecast,
    f.absolute_error,
    f.squared_error,
    f.forecast_agent_demand_calls - f.actual_agent_demand_calls AS forecast_minus_actual,
    f.data_origin,
    f.etl_run_id
FROM analytics.fact_forecast_interval AS f
JOIN analytics.dim_date AS d ON d.date_key = f.target_date_key
JOIN analytics.dim_time_interval AS ti ON ti.interval_key = f.target_interval_key
JOIN analytics.dim_queue AS q ON q.queue_id = f.queue_id;

CREATE OR REPLACE VIEW analytics.vw_kpi_forecast_weekly_model AS
SELECT
    d.week_start_date AS target_week_start_date,
    f.queue_id,
    f.model_name,
    f.model_version,
    f.forecast_type,
    f.backtest_fold,
    f.is_selected_model,
    COUNT(*) AS evaluated_intervals,
    SUM(f.actual_agent_demand_calls) AS actual_calls,
    SUM(f.forecast_agent_demand_calls) AS forecast_calls,
    AVG(f.absolute_error) AS mae,
    SQRT(AVG(f.squared_error)) AS rmse,
    SUM(f.absolute_error) / NULLIF(SUM(f.actual_agent_demand_calls), 0)
        AS wape,
    SUM(f.forecast_agent_demand_calls - f.actual_agent_demand_calls)
        / NULLIF(SUM(f.actual_agent_demand_calls), 0) AS bias
FROM analytics.fact_forecast_interval AS f
JOIN analytics.dim_date AS d ON d.date_key = f.target_date_key
GROUP BY
    d.week_start_date, f.queue_id, f.model_name, f.model_version,
    f.forecast_type, f.backtest_fold, f.is_selected_model;

CREATE OR REPLACE VIEW analytics.vw_powerbi_model_evaluation AS
SELECT
    model_name,
    model_version,
    forecast_type,
    evaluation_scope,
    backtest_fold,
    training_start_date,
    training_end_date,
    test_start,
    test_end,
    evaluated_intervals,
    actual_sum,
    forecast_sum,
    mae,
    rmse,
    wape,
    bias,
    is_selected_model,
    data_origin
FROM analytics.fact_model_evaluation;

CREATE OR REPLACE VIEW analytics.vw_powerbi_staffing_interval AS
SELECT
    s.target_local_interval_start,
    s.target_date_key,
    d.calendar_date,
    d.week_start_date,
    d.day_of_week_iso,
    d.day_name,
    d.is_holiday,
    s.target_interval_key,
    ti.interval_number,
    ti.start_time,
    ti.daypart,
    s.queue_id,
    q.queue_name,
    s.forecast_run_id,
    s.model_name,
    s.forecast_agent_demand_calls,
    s.forecast_aht_proxy_seconds,
    s.workload_hours,
    s.occupancy_target,
    s.shrinkage_rate,
    s.required_productive_agents,
    s.required_scheduled_agents,
    s.required_productive_agents * s.interval_minutes / 60.0
        AS required_productive_agent_hours,
    s.required_scheduled_agents * s.interval_minutes / 60.0
        AS required_scheduled_agent_hours,
    s.actual_agent_demand_calls,
    s.actual_aht_proxy_seconds,
    s.actualized_workload_hours,
    s.actualized_productive_agents,
    s.actualized_scheduled_agents,
    s.actualized_productive_agents - s.required_productive_agents
        AS actualized_minus_planned_productive_agents,
    s.actualized_scheduled_agents - s.required_scheduled_agents
        AS actualized_minus_planned_scheduled_agents,
    s.actualized_analysis_only,
    s.is_operating_interval,
    s.staffing_method,
    s.assumption_version,
    s.data_origin
FROM analytics.fact_staffing_requirement AS s
JOIN analytics.dim_date AS d ON d.date_key = s.target_date_key
JOIN analytics.dim_time_interval AS ti ON ti.interval_key = s.target_interval_key
JOIN analytics.dim_queue AS q ON q.queue_id = s.queue_id;

CREATE OR REPLACE VIEW analytics.vw_kpi_staffing_daily AS
SELECT
    s.target_date_key,
    d.calendar_date,
    d.week_start_date,
    d.day_of_week_iso,
    d.day_name,
    s.queue_id,
    s.model_name,
    SUM(s.forecast_agent_demand_calls) AS forecast_agent_demand_calls,
    SUM(s.actual_agent_demand_calls) AS actual_agent_demand_calls,
    SUM(s.workload_hours) AS planned_workload_hours,
    SUM(s.actualized_workload_hours) AS actualized_workload_hours,
    MAX(s.required_productive_agents) AS peak_required_productive_agents,
    MAX(s.required_scheduled_agents) AS peak_required_scheduled_agents,
    SUM(s.required_productive_agents * s.interval_minutes / 60.0)
        AS required_productive_agent_hours,
    SUM(s.required_scheduled_agents * s.interval_minutes / 60.0)
        AS required_scheduled_agent_hours,
    COUNT(*) FILTER (WHERE s.required_scheduled_agents > 0)
        AS intervals_requiring_staff
FROM analytics.fact_staffing_requirement AS s
JOIN analytics.dim_date AS d ON d.date_key = s.target_date_key
GROUP BY
    s.target_date_key, d.calendar_date, d.week_start_date,
    d.day_of_week_iso, d.day_name, s.queue_id, s.model_name;

CREATE OR REPLACE VIEW analytics.vw_powerbi_refresh_status AS
SELECT
    load_id,
    loaded_at_utc,
    loader_version,
    source_directory,
    table_row_counts,
    source_sha256,
    database_name,
    database_user_name
FROM analytics.mart_load_audit
ORDER BY load_id DESC;

COMMENT ON VIEW analytics.vw_powerbi_staffing_interval IS
    'Planned requirement plus retrospective actualized requirement. No scheduled or available workforce exists yet, so this is not a staffing-gap view.';
COMMENT ON VIEW analytics.vw_kpi_daily_queue IS
    'Daily queue KPIs calculated from additive numerators and denominators; ratios are never averages of interval rates.';
