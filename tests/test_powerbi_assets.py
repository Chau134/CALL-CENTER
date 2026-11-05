import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_powerbi_theme_is_valid_json_with_locked_colors() -> None:
    theme = json.loads(
        (PROJECT_ROOT / "powerbi" / "call_center_wfm_theme.json").read_text(
            encoding="utf-8"
        )
    )
    assert theme["name"] == "Call Center WFM Analytics"
    assert theme["dataColors"][:4] == [
        "#1F4E78",
        "#F28E2B",
        "#2A9D8F",
        "#D9534F",
    ]


def test_dax_library_contains_required_measure_groups() -> None:
    dax = (PROJECT_ROOT / "powerbi" / "measures.dax").read_text(encoding="utf-8")
    for measure in (
        "Offered Calls =",
        "Service Level =",
        "Selected Forecast WAPE =",
        "Model WAPE (All Folds) =",
        "Peak Scheduled Agents =",
        "Service AHT Proxy Seconds =",
        "Last Warehouse Load =",
    ):
        assert measure in dax


def test_powerbi_qa_sql_covers_duplicate_and_reconciliation_risks() -> None:
    sql = (PROJECT_ROOT / "sql" / "04_powerbi_model_qa.sql").read_text(
        encoding="utf-8"
    )
    assert "COUNT(DISTINCT (target_date_key, target_interval_key, queue_id))" in sql
    assert "backtest_fold = 'ALL'" in sql
    assert "service_totals" in sql
