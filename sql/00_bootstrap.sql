-- Run after connecting to the call_center_wfm database.
-- This script is safe to run more than once.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;

COMMENT ON SCHEMA raw IS
    'Immutable or minimally transformed source data.';
COMMENT ON SCHEMA staging IS
    'Validated and standardized intermediate data.';
COMMENT ON SCHEMA analytics IS
    'Dimensions, facts, KPI views, and Power BI serving objects.';
