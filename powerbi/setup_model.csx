// Tabular Editor 2 advanced script for the Call Center WFM Power BI model.
// Safe to rerun: generated measures are updated in place.

var requiredTables = new[] {
    "dim_date",
    "dim_time_interval",
    "dim_queue",
    "dim_service_type",
    "fact_queue_interval_complete",
    "fact_service_type_interval",
    "fact_forecast_interval",
    "fact_model_evaluation",
    "fact_staffing_requirement",
    "vw_powerbi_refresh_status"
};

// Power BI's PostgreSQL navigator may prefix imported table names with
// "analytics ". Normalize only the managed warehouse objects; partition
// source expressions remain unchanged.
foreach (var canonicalName in requiredTables)
{
    var canonicalTable = Model.Tables.FirstOrDefault(table => table.Name == canonicalName);
    var importedTable = Model.Tables.FirstOrDefault(
        table => table.Name == "analytics " + canonicalName
    );

    if (canonicalTable == null && importedTable != null)
    {
        importedTable.Name = canonicalName;
    }
}

var missingTables = requiredTables
    .Where(name => Model.Tables.FirstOrDefault(table => table.Name == name) == null)
    .ToList();
if (missingTables.Count > 0)
{
    throw new Exception(
        "Missing required Power BI tables: " + string.Join(", ", missingTables)
    );
}

var measureTable = Model.Tables.FirstOrDefault(table => table.Name == "_Measures");
if (measureTable == null)
{
    measureTable = Model.AddCalculatedTable("_Measures", "{0}");
    measureTable.Description = "Central measure table for Call Center WFM analytics.";
}

Action<string, string, string, string, string> upsertMeasure =
    (name, expression, folder, formatString, description) =>
    {
        var measure = measureTable.Measures.FirstOrDefault(item => item.Name == name);
        if (measure == null)
        {
            measure = measureTable.AddMeasure(name, expression, folder);
        }
        else
        {
            measure.Expression = expression;
            measure.DisplayFolder = folder;
        }
        measure.FormatString = formatString;
        measure.Description = description;
        measure.SetAnnotation("CALL_CENTER_WFM_AUTOGEN", "1");
    };

// Queue measures
upsertMeasure("Offered Calls",
    "SUM('fact_queue_interval_complete'[offered_calls])",
    "01 Queue KPIs", "#,0", "All clean inbound calls entering the VRU.");
upsertMeasure("Agent Demand Calls",
    "SUM('fact_queue_interval_complete'[agent_demand_calls])",
    "01 Queue KPIs", "#,0", "Answered plus queue-abandoned calls; staffing forecast target.");
upsertMeasure("Answered Calls",
    "SUM('fact_queue_interval_complete'[answered_calls])",
    "01 Queue KPIs", "#,0", "Answered calls.");
upsertMeasure("Abandoned Calls",
    "SUM('fact_queue_interval_complete'[abandoned_calls])",
    "01 Queue KPIs", "#,0", "All abandoned calls, including short abandons.");
upsertMeasure("Queue Abandoned Calls",
    "SUM('fact_queue_interval_complete'[queue_abandoned_calls])",
    "01 Queue KPIs", "#,0", "Abandoned calls that reached the agent queue.");
upsertMeasure("VRU Abandoned Calls",
    "SUM('fact_queue_interval_complete'[vru_abandoned_calls])",
    "01 Queue KPIs", "#,0", "Abandoned calls that did not reach the queue.");
upsertMeasure("Short Abandoned Calls",
    "SUM('fact_queue_interval_complete'[short_abandon_calls])",
    "01 Queue KPIs", "#,0", "Abandoned calls with wait time at most five seconds.");
upsertMeasure("Answer Rate",
    "DIVIDE([Answered Calls], [Offered Calls])",
    "01 Queue KPIs", "0.00%", "Answered calls divided by offered calls.");
upsertMeasure("Abandon Rate",
    "DIVIDE([Abandoned Calls], [Offered Calls])",
    "01 Queue KPIs", "0.00%", "Abandoned calls divided by offered calls.");
upsertMeasure("Short Abandon Rate",
    "DIVIDE([Short Abandoned Calls], [Offered Calls])",
    "01 Queue KPIs", "0.00%", "Short abandoned calls divided by offered calls.");
upsertMeasure("Service Level",
    "DIVIDE(SUM('fact_queue_interval_complete'[answered_within_20s]), SUM('fact_queue_interval_complete'[service_level_denominator]))",
    "01 Queue KPIs", "0.00%", "Answered within 20 seconds divided by eligible offered calls, excluding short abandons.");
upsertMeasure("AHT Proxy Seconds",
    "DIVIDE(SUM('fact_queue_interval_complete'[total_service_seconds_for_aht]), SUM('fact_queue_interval_complete'[aht_eligible_calls]))",
    "01 Queue KPIs", "#,0.00", "Service-time proxy; source lacks hold and ACW.");
upsertMeasure("Average Wait Seconds All Calls",
    "DIVIDE(SUM('fact_queue_interval_complete'[total_wait_seconds]), [Offered Calls])",
    "01 Queue KPIs", "#,0.00", "Average wait across all clean calls; not ASA.");

// Forecast measures
upsertMeasure("Selected Model Name",
    @"CALCULATE(
        SELECTEDVALUE('fact_model_evaluation'[model_name]),
        'fact_model_evaluation'[is_selected_model] = TRUE(),
        'fact_model_evaluation'[backtest_fold] = ""ALL"",
        'fact_model_evaluation'[evaluation_scope] = ""overall""
    )",
    "02 Forecast", "", "Model selected by aggregate WAPE, absolute bias, then MAE.");
upsertMeasure("Selected Forecast Calls",
    "CALCULATE(SUM('fact_forecast_interval'[forecast_agent_demand_calls]), 'fact_forecast_interval'[is_selected_model] = TRUE())",
    "02 Forecast", "#,0.00", "Selected-model forecast calls across non-overlapping backtest targets.");
upsertMeasure("Selected Forecast Actual",
    "CALCULATE(SUM('fact_forecast_interval'[actual_agent_demand_calls]), 'fact_forecast_interval'[is_selected_model] = TRUE())",
    "02 Forecast", "#,0", "Actual calls paired with selected-model target rows.");
upsertMeasure("Selected Forecast Absolute Error",
    "CALCULATE(SUM('fact_forecast_interval'[absolute_error]), 'fact_forecast_interval'[is_selected_model] = TRUE())",
    "02 Forecast", "#,0.00", "Total selected-model absolute error.");
upsertMeasure("Selected Forecast WAPE",
    "DIVIDE([Selected Forecast Absolute Error], [Selected Forecast Actual])",
    "02 Forecast", "0.00%", "Selected-model WAPE over interval rows in filter context.");
upsertMeasure("Selected Forecast Bias",
    "DIVIDE([Selected Forecast Calls] - [Selected Forecast Actual], [Selected Forecast Actual])",
    "02 Forecast", "0.00%", "Forecast minus actual divided by actual; negative means under-forecast.");
upsertMeasure("Selected Forecast MAE",
    "CALCULATE(AVERAGE('fact_forecast_interval'[absolute_error]), 'fact_forecast_interval'[is_selected_model] = TRUE())",
    "02 Forecast", "#,0.00", "Selected-model mean absolute error.");
upsertMeasure("Selected Forecast RMSE",
    @"VAR MeanSquaredError =
        CALCULATE(
            AVERAGE('fact_forecast_interval'[squared_error]),
            'fact_forecast_interval'[is_selected_model] = TRUE()
        )
    RETURN SQRT(MeanSquaredError)",
    "02 Forecast", "#,0.00", "Selected-model root mean squared error.");
upsertMeasure("Model WAPE (All Folds)",
    "CALCULATE(MAX('fact_model_evaluation'[wape]), 'fact_model_evaluation'[backtest_fold] = \"ALL\", 'fact_model_evaluation'[evaluation_scope] = \"overall\")",
    "02 Forecast\\Model Comparison", "0.00%", "Aggregate overall WAPE scalar for each model.");
upsertMeasure("Model Bias (All Folds)",
    "CALCULATE(MAX('fact_model_evaluation'[bias]), 'fact_model_evaluation'[backtest_fold] = \"ALL\", 'fact_model_evaluation'[evaluation_scope] = \"overall\")",
    "02 Forecast\\Model Comparison", "0.00%", "Aggregate overall bias scalar for each model.");
upsertMeasure("Model MAE (All Folds)",
    "CALCULATE(MAX('fact_model_evaluation'[mae]), 'fact_model_evaluation'[backtest_fold] = \"ALL\", 'fact_model_evaluation'[evaluation_scope] = \"overall\")",
    "02 Forecast\\Model Comparison", "#,0.00", "Aggregate overall MAE scalar for each model.");
upsertMeasure("Model RMSE (All Folds)",
    "CALCULATE(MAX('fact_model_evaluation'[rmse]), 'fact_model_evaluation'[backtest_fold] = \"ALL\", 'fact_model_evaluation'[evaluation_scope] = \"overall\")",
    "02 Forecast\\Model Comparison", "#,0.00", "Aggregate overall RMSE scalar for each model.");

// Staffing measures
upsertMeasure("Planned Workload Hours",
    "SUM('fact_staffing_requirement'[workload_hours])",
    "03 Staffing", "#,0.00", "Forecast-driven workload hours.");
upsertMeasure("Actualized Workload Hours",
    "SUM('fact_staffing_requirement'[actualized_workload_hours])",
    "03 Staffing", "#,0.00", "Retrospective actualized workload; not planning information.");
upsertMeasure("Peak Productive Agents",
    "MAX('fact_staffing_requirement'[required_productive_agents])",
    "03 Staffing", "#,0", "Peak productive requirement for the current one-queue selected-run MVP.");
upsertMeasure("Peak Scheduled Agents",
    "MAX('fact_staffing_requirement'[required_scheduled_agents])",
    "03 Staffing", "#,0", "Peak scheduled requirement after shrinkage for current MVP.");
upsertMeasure("Required Productive Agent Hours",
    "SUMX('fact_staffing_requirement', 'fact_staffing_requirement'[required_productive_agents] * 'fact_staffing_requirement'[interval_minutes] / 60)",
    "03 Staffing", "#,0.00", "Sum of productive requirement times interval hours.");
upsertMeasure("Required Scheduled Agent Hours",
    "SUMX('fact_staffing_requirement', 'fact_staffing_requirement'[required_scheduled_agents] * 'fact_staffing_requirement'[interval_minutes] / 60)",
    "03 Staffing", "#,0.00", "Sum of scheduled requirement times interval hours.");
upsertMeasure("Intervals Requiring Staff",
    "CALCULATE(COUNTROWS('fact_staffing_requirement'), 'fact_staffing_requirement'[required_scheduled_agents] > 0)",
    "03 Staffing", "#,0", "Count of unique staffing rows with scheduled requirement above zero in current MVP grain.");

// Service-type measures
upsertMeasure("Service Offered Calls",
    "SUM('fact_service_type_interval'[offered_calls])",
    "04 Service Type", "#,0", "Offered calls in service-type fact.");
upsertMeasure("Service Agent Demand Calls",
    "SUM('fact_service_type_interval'[agent_demand_calls])",
    "04 Service Type", "#,0", "Agent demand calls in service-type fact.");
upsertMeasure("Service Answered Calls",
    "SUM('fact_service_type_interval'[answered_calls])",
    "04 Service Type", "#,0", "Answered calls in service-type fact.");
upsertMeasure("Service Abandoned Calls",
    "SUM('fact_service_type_interval'[abandoned_calls])",
    "04 Service Type", "#,0", "Abandoned calls in service-type fact.");
upsertMeasure("Service Answer Rate",
    "DIVIDE([Service Answered Calls], [Service Offered Calls])",
    "04 Service Type", "0.00%", "Service-type answered divided by service-type offered.");
upsertMeasure("Service Abandon Rate",
    "DIVIDE([Service Abandoned Calls], [Service Offered Calls])",
    "04 Service Type", "0.00%", "Service-type abandoned divided by service-type offered.");
upsertMeasure("Service AHT Proxy Seconds",
    "DIVIDE(SUM('fact_service_type_interval'[service_seconds_sum_for_aht]), SUM('fact_service_type_interval'[valid_for_aht_calls]))",
    "04 Service Type", "#,0.00", "Weighted service-time proxy by service type.");

// Refresh metadata
upsertMeasure("Last Warehouse Load",
    "MAX('vw_powerbi_refresh_status'[loaded_at_utc])",
    "05 Data Quality", "yyyy-mm-dd hh:mm", "Latest successful PostgreSQL mart load timestamp.");

// Hide technical columns while retaining them for relationships and QA.
var technicalColumns = new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
    "date_key", "interval_key", "target_date_key", "target_interval_key",
    "etl_run_id", "generation_method", "generation_version",
    "source_reference", "source_fact"
};
foreach (var table in Model.Tables)
{
    foreach (var column in table.Columns)
    {
        if (technicalColumns.Contains(column.Name)) column.IsHidden = true;
    }
}

// Sort labels using stable numeric columns.
Model.Tables["dim_date"].Columns["day_name"].SortByColumn =
    Model.Tables["dim_date"].Columns["day_of_week_iso"];
Model.Tables["dim_date"].Columns["month_name"].SortByColumn =
    Model.Tables["dim_date"].Columns["month_number"];
Model.Tables["dim_time_interval"].Columns["start_time"].SortByColumn =
    Model.Tables["dim_time_interval"].Columns["interval_number"];

// Mark the canonical date table metadata.
Model.Tables["dim_date"].DataCategory = "Time";
Model.Tables["dim_date"].Columns["calendar_date"].IsKey = true;

Model.DiscourageImplicitMeasures = true;
Model.SetAnnotation("CALL_CENTER_WFM_SETUP_VERSION", "1.0.0");
Info("Call Center WFM semantic-model setup completed.");
