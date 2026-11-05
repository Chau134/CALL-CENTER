-- Analytics warehouse schema for the Call Center WFM project.
-- Safe to rerun: objects are created only when absent.

CREATE SCHEMA IF NOT EXISTS analytics;

CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key integer PRIMARY KEY,
    calendar_date date NOT NULL UNIQUE,
    day_of_week_iso smallint NOT NULL CHECK (day_of_week_iso BETWEEN 1 AND 7),
    day_name varchar(12) NOT NULL,
    day_of_month smallint NOT NULL CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_year smallint NOT NULL CHECK (day_of_year BETWEEN 1 AND 366),
    week_of_year smallint NOT NULL CHECK (week_of_year BETWEEN 1 AND 53),
    week_start_date date NOT NULL,
    month_number smallint NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    month_name varchar(12) NOT NULL,
    quarter_number smallint NOT NULL CHECK (quarter_number BETWEEN 1 AND 4),
    year_number smallint NOT NULL,
    is_weekend boolean NOT NULL,
    is_operating_day boolean NOT NULL,
    is_holiday boolean NOT NULL,
    holiday_name varchar(160),
    holiday_type varchar(80),
    is_major_holiday boolean NOT NULL,
    is_calendar_day_before_holiday boolean NOT NULL,
    is_calendar_day_after_holiday boolean NOT NULL,
    holiday_data_origin varchar(80),
    holiday_source_reference text,
    is_dst_transition_day boolean NOT NULL,
    data_origin varchar(80) NOT NULL,
    generation_method varchar(80) NOT NULL,
    generation_version varchar(20) NOT NULL,
    etl_run_id varchar(80) NOT NULL,
    CHECK (date_key = (extract(year FROM calendar_date)::integer * 10000
        + extract(month FROM calendar_date)::integer * 100
        + extract(day FROM calendar_date)::integer))
);

CREATE TABLE IF NOT EXISTS analytics.dim_time_interval (
    interval_key smallint PRIMARY KEY,
    interval_number smallint NOT NULL UNIQUE CHECK (interval_number BETWEEN 0 AND 47),
    start_time time NOT NULL UNIQUE,
    end_time time NOT NULL,
    interval_minutes smallint NOT NULL CHECK (interval_minutes = 30),
    hour_number smallint NOT NULL CHECK (hour_number BETWEEN 0 AND 23),
    minute_number smallint NOT NULL CHECK (minute_number IN (0, 30)),
    daypart varchar(20) NOT NULL,
    data_origin varchar(80) NOT NULL,
    generation_method varchar(80) NOT NULL,
    generation_version varchar(20) NOT NULL,
    etl_run_id varchar(80) NOT NULL
);

CREATE TABLE IF NOT EXISTS analytics.dim_queue (
    queue_id varchar(64) PRIMARY KEY,
    queue_name varchar(160) NOT NULL,
    channel varchar(40) NOT NULL,
    direction varchar(20) NOT NULL,
    timezone varchar(64) NOT NULL,
    is_active boolean NOT NULL,
    valid_from date NOT NULL,
    valid_to date NOT NULL,
    data_origin varchar(80) NOT NULL,
    generation_method varchar(80) NOT NULL,
    generation_version varchar(20) NOT NULL,
    etl_run_id varchar(80) NOT NULL,
    CHECK (valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS analytics.dim_service_type (
    service_type_code varchar(40) PRIMARY KEY,
    service_type_name varchar(160) NOT NULL,
    queue_id varchar(64) NOT NULL REFERENCES analytics.dim_queue(queue_id),
    is_valid boolean NOT NULL,
    valid_from date NOT NULL,
    valid_to date NOT NULL,
    data_origin varchar(80) NOT NULL,
    source_reference text NOT NULL,
    generation_method varchar(80) NOT NULL,
    generation_version varchar(20) NOT NULL,
    etl_run_id varchar(80) NOT NULL,
    UNIQUE (service_type_code, queue_id),
    CHECK (valid_to >= valid_from)
);

CREATE TABLE IF NOT EXISTS analytics.fact_queue_interval_complete (
    date_key integer NOT NULL REFERENCES analytics.dim_date(date_key),
    interval_key smallint NOT NULL REFERENCES analytics.dim_time_interval(interval_key),
    queue_id varchar(64) NOT NULL REFERENCES analytics.dim_queue(queue_id),
    local_interval_start timestamp NOT NULL,
    local_interval_end timestamp NOT NULL,
    interval_start_assumed timestamptz,
    interval_end_assumed timestamptz,
    interval_start_utc timestamptz,
    interval_end_utc timestamptz,
    actual_interval_seconds numeric(10,3),
    source_timezone varchar(64) NOT NULL,
    interval_minutes smallint NOT NULL CHECK (interval_minutes = 30),
    channel varchar(40) NOT NULL,
    direction varchar(20) NOT NULL,
    raw_record_count integer NOT NULL CHECK (raw_record_count >= 0),
    excluded_record_count integer NOT NULL CHECK (excluded_record_count >= 0),
    quarantine_record_count integer NOT NULL CHECK (quarantine_record_count >= 0),
    has_source_records boolean NOT NULL,
    has_calls boolean NOT NULL,
    source_file_available boolean NOT NULL,
    source_date_covered boolean NOT NULL,
    interval_coverage_verified boolean NOT NULL,
    source_period_covered boolean NOT NULL,
    is_operating_interval boolean NOT NULL,
    is_closed_interval boolean NOT NULL,
    coverage_status varchar(40) NOT NULL,
    zero_fill_reason varchar(80),
    dst_transition_flag boolean NOT NULL,
    dst_status varchar(40) NOT NULL,
    offered_calls integer NOT NULL CHECK (offered_calls >= 0),
    agent_demand_calls integer NOT NULL CHECK (agent_demand_calls >= 0),
    answered_calls integer NOT NULL CHECK (answered_calls >= 0),
    abandoned_calls integer NOT NULL CHECK (abandoned_calls >= 0),
    queue_abandoned_calls integer NOT NULL CHECK (queue_abandoned_calls >= 0),
    vru_abandoned_calls integer NOT NULL CHECK (vru_abandoned_calls >= 0),
    short_abandon_calls integer NOT NULL CHECK (short_abandon_calls >= 0),
    answered_within_20s integer NOT NULL CHECK (answered_within_20s >= 0),
    service_level_denominator integer NOT NULL CHECK (service_level_denominator >= 0),
    service_level_rate numeric(12,8) CHECK (service_level_rate BETWEEN 0 AND 1),
    total_wait_seconds bigint NOT NULL CHECK (total_wait_seconds >= 0),
    avg_wait_seconds numeric(14,6) CHECK (avg_wait_seconds >= 0),
    aht_eligible_calls integer NOT NULL CHECK (aht_eligible_calls >= 0),
    total_service_seconds_for_aht bigint NOT NULL CHECK (total_service_seconds_for_aht >= 0),
    aht_proxy_seconds numeric(14,6) CHECK (aht_proxy_seconds >= 0),
    data_origin varchar(80) NOT NULL,
    source_reference text NOT NULL,
    generation_method varchar(80) NOT NULL,
    generation_version varchar(20) NOT NULL,
    etl_run_id varchar(80) NOT NULL,
    PRIMARY KEY (date_key, interval_key, queue_id),
    UNIQUE (queue_id, local_interval_start),
    CHECK (local_interval_end > local_interval_start),
    CHECK (is_operating_interval <> is_closed_interval),
    CHECK (offered_calls = answered_calls + abandoned_calls),
    CHECK (agent_demand_calls = answered_calls + queue_abandoned_calls),
    CHECK (abandoned_calls = queue_abandoned_calls + vru_abandoned_calls),
    CHECK (short_abandon_calls <= abandoned_calls),
    CHECK (answered_within_20s <= answered_calls)
);

CREATE TABLE IF NOT EXISTS analytics.fact_service_type_interval (
    date_key integer NOT NULL REFERENCES analytics.dim_date(date_key),
    interval_key smallint NOT NULL REFERENCES analytics.dim_time_interval(interval_key),
    service_type_code varchar(40) NOT NULL,
    service_type_name varchar(160) NOT NULL,
    queue_id varchar(64) NOT NULL,
    local_interval_start timestamp NOT NULL,
    source_timezone varchar(64) NOT NULL,
    coverage_status varchar(40) NOT NULL,
    is_operating_interval boolean NOT NULL,
    offered_calls integer NOT NULL CHECK (offered_calls >= 0),
    agent_demand_calls integer NOT NULL CHECK (agent_demand_calls >= 0),
    answered_calls integer NOT NULL CHECK (answered_calls >= 0),
    abandoned_calls integer NOT NULL CHECK (abandoned_calls >= 0),
    queue_abandoned_calls integer NOT NULL CHECK (queue_abandoned_calls >= 0),
    vru_abandoned_calls integer NOT NULL CHECK (vru_abandoned_calls >= 0),
    short_abandon_calls integer NOT NULL CHECK (short_abandon_calls >= 0),
    answered_within_20s integer NOT NULL CHECK (answered_within_20s >= 0),
    valid_for_aht_calls integer NOT NULL CHECK (valid_for_aht_calls >= 0),
    wait_seconds_sum bigint NOT NULL CHECK (wait_seconds_sum >= 0),
    service_seconds_sum_for_aht bigint NOT NULL CHECK (service_seconds_sum_for_aht >= 0),
    aht_proxy_seconds numeric(14,6) CHECK (aht_proxy_seconds >= 0),
    data_origin varchar(80) NOT NULL,
    source_reference text NOT NULL,
    generation_method varchar(80) NOT NULL,
    generation_version varchar(20) NOT NULL,
    etl_run_id varchar(80) NOT NULL,
    PRIMARY KEY (date_key, interval_key, service_type_code, queue_id),
    FOREIGN KEY (service_type_code, queue_id)
        REFERENCES analytics.dim_service_type(service_type_code, queue_id),
    CHECK (offered_calls = answered_calls + abandoned_calls),
    CHECK (agent_demand_calls = answered_calls + queue_abandoned_calls),
    CHECK (abandoned_calls = queue_abandoned_calls + vru_abandoned_calls),
    CHECK (short_abandon_calls <= abandoned_calls),
    CHECK (answered_within_20s <= answered_calls)
);

CREATE TABLE IF NOT EXISTS analytics.fact_forecast_interval (
    forecast_run_id varchar(160) NOT NULL,
    forecast_generated_at timestamp NOT NULL,
    artifact_generated_at_utc timestamptz NOT NULL,
    target_local_interval_start timestamp NOT NULL,
    target_date_key integer NOT NULL REFERENCES analytics.dim_date(date_key),
    target_interval_key smallint NOT NULL REFERENCES analytics.dim_time_interval(interval_key),
    queue_id varchar(64) NOT NULL REFERENCES analytics.dim_queue(queue_id),
    target_metric varchar(64) NOT NULL,
    model_name varchar(120) NOT NULL,
    model_version varchar(20) NOT NULL,
    training_start_date date NOT NULL,
    training_end_date timestamp NOT NULL,
    forecast_agent_demand_calls numeric(14,6) NOT NULL CHECK (forecast_agent_demand_calls >= 0),
    actual_agent_demand_calls integer NOT NULL CHECK (actual_agent_demand_calls >= 0),
    forecast_aht_proxy_seconds numeric(14,6) NOT NULL CHECK (forecast_aht_proxy_seconds > 0),
    actual_aht_proxy_seconds numeric(14,6) CHECK (actual_aht_proxy_seconds >= 0),
    error_actual_minus_forecast numeric(14,6) NOT NULL,
    absolute_error numeric(14,6) NOT NULL CHECK (absolute_error >= 0),
    squared_error numeric(20,6) NOT NULL CHECK (squared_error >= 0),
    percentage_error numeric(18,8),
    backtest_fold smallint NOT NULL CHECK (backtest_fold > 0),
    forecast_horizon_intervals smallint NOT NULL CHECK (forecast_horizon_intervals > 0),
    forecast_type varchar(20) NOT NULL,
    forecast_quantile numeric(8,6) CHECK (forecast_quantile BETWEEN 0 AND 1),
    evaluation_status varchar(30) NOT NULL,
    is_selected_model boolean NOT NULL,
    is_operating_interval boolean NOT NULL,
    data_origin varchar(80) NOT NULL,
    source_fact varchar(80) NOT NULL,
    etl_run_id varchar(80) NOT NULL,
    PRIMARY KEY (forecast_run_id, target_date_key, target_interval_key, queue_id),
    UNIQUE (forecast_run_id, target_local_interval_start, queue_id),
    CHECK (target_local_interval_start > training_end_date)
);

CREATE TABLE IF NOT EXISTS analytics.fact_model_evaluation (
    model_name varchar(120) NOT NULL,
    model_version varchar(20) NOT NULL,
    forecast_type varchar(20) NOT NULL,
    evaluation_scope varchar(20) NOT NULL,
    backtest_fold varchar(8) NOT NULL,
    training_start_date date NOT NULL,
    training_end_date timestamp NOT NULL,
    test_start timestamp NOT NULL,
    test_end timestamp NOT NULL,
    evaluated_intervals integer NOT NULL CHECK (evaluated_intervals > 0),
    actual_sum numeric(18,6) NOT NULL CHECK (actual_sum >= 0),
    forecast_sum numeric(18,6) NOT NULL CHECK (forecast_sum >= 0),
    mae numeric(14,6) NOT NULL CHECK (mae >= 0),
    rmse numeric(14,6) NOT NULL CHECK (rmse >= 0),
    wape numeric(14,8) CHECK (wape >= 0),
    bias numeric(14,8),
    is_selected_model boolean NOT NULL,
    data_origin varchar(80) NOT NULL,
    PRIMARY KEY (model_name, model_version, evaluation_scope, backtest_fold),
    CHECK (test_end >= test_start),
    CHECK (backtest_fold = 'ALL' OR test_start > training_end_date)
);

CREATE TABLE IF NOT EXISTS analytics.fact_staffing_requirement (
    target_local_interval_start timestamp NOT NULL,
    target_date_key integer NOT NULL REFERENCES analytics.dim_date(date_key),
    target_interval_key smallint NOT NULL REFERENCES analytics.dim_time_interval(interval_key),
    queue_id varchar(64) NOT NULL REFERENCES analytics.dim_queue(queue_id),
    forecast_run_id varchar(160) NOT NULL,
    model_name varchar(120) NOT NULL,
    target_metric varchar(64) NOT NULL,
    forecast_agent_demand_calls numeric(14,6) NOT NULL CHECK (forecast_agent_demand_calls >= 0),
    forecast_aht_proxy_seconds numeric(14,6) NOT NULL CHECK (forecast_aht_proxy_seconds > 0),
    workload_hours numeric(14,6) NOT NULL CHECK (workload_hours >= 0),
    interval_minutes smallint NOT NULL CHECK (interval_minutes = 30),
    occupancy_target numeric(8,6) NOT NULL CHECK (occupancy_target > 0 AND occupancy_target <= 1),
    shrinkage_rate numeric(8,6) NOT NULL CHECK (shrinkage_rate >= 0 AND shrinkage_rate < 1),
    required_productive_agents integer NOT NULL CHECK (required_productive_agents >= 0),
    required_scheduled_agents integer NOT NULL CHECK (required_scheduled_agents >= 0),
    staffing_method varchar(60) NOT NULL,
    assumption_version varchar(40) NOT NULL,
    actual_agent_demand_calls integer NOT NULL CHECK (actual_agent_demand_calls >= 0),
    actual_aht_proxy_seconds numeric(14,6) CHECK (actual_aht_proxy_seconds >= 0),
    actualized_workload_hours numeric(14,6) CHECK (actualized_workload_hours >= 0),
    actualized_productive_agents numeric(10,3) CHECK (actualized_productive_agents >= 0),
    actualized_scheduled_agents numeric(10,3) CHECK (actualized_scheduled_agents >= 0),
    actualized_analysis_only boolean NOT NULL,
    is_operating_interval boolean NOT NULL,
    data_origin varchar(80) NOT NULL,
    PRIMARY KEY (forecast_run_id, target_date_key, target_interval_key, queue_id),
    FOREIGN KEY (forecast_run_id, target_date_key, target_interval_key, queue_id)
        REFERENCES analytics.fact_forecast_interval(
            forecast_run_id, target_date_key, target_interval_key, queue_id
        )
);

CREATE TABLE IF NOT EXISTS analytics.mart_load_audit (
    load_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    loaded_at_utc timestamptz NOT NULL DEFAULT now(),
    loader_version varchar(20) NOT NULL,
    source_directory text NOT NULL,
    table_row_counts jsonb NOT NULL,
    source_sha256 jsonb NOT NULL,
    database_name text NOT NULL DEFAULT current_database(),
    database_user_name text NOT NULL DEFAULT current_user
);

CREATE INDEX IF NOT EXISTS ix_queue_interval_queue_date
    ON analytics.fact_queue_interval_complete (queue_id, date_key, interval_key);
CREATE INDEX IF NOT EXISTS ix_queue_interval_local_start
    ON analytics.fact_queue_interval_complete (local_interval_start);
CREATE INDEX IF NOT EXISTS ix_service_interval_service_date
    ON analytics.fact_service_type_interval (service_type_code, date_key, interval_key);
CREATE INDEX IF NOT EXISTS ix_forecast_target_model
    ON analytics.fact_forecast_interval (target_date_key, target_interval_key, model_name);
CREATE INDEX IF NOT EXISTS ix_forecast_selected
    ON analytics.fact_forecast_interval (target_date_key, queue_id)
    WHERE is_selected_model;
CREATE INDEX IF NOT EXISTS ix_evaluation_model_scope
    ON analytics.fact_model_evaluation (model_name, evaluation_scope, backtest_fold);
CREATE INDEX IF NOT EXISTS ix_staffing_target
    ON analytics.fact_staffing_requirement (target_date_key, target_interval_key, queue_id);

COMMENT ON TABLE analytics.fact_queue_interval_complete IS
    'Observed and derived queue metrics at date x 30-minute interval x queue grain.';
COMMENT ON TABLE analytics.fact_forecast_interval IS
    'Rolling-origin point forecasts and actuals at forecast run x target interval x queue grain.';
COMMENT ON TABLE analytics.fact_staffing_requirement IS
    'Capacity-based planned requirement; actualized fields are retrospective analysis only.';
