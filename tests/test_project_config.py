from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "project.yml"


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def test_config_has_locked_mvp_scope() -> None:
    config = load_config()

    assert config["project"]["timezone"] == "Asia/Jerusalem"
    assert config["scope"]["channel"] == "inbound_voice"
    assert config["scope"]["interval_minutes"] == 30
    assert config["forecast"]["horizon_days"] == 7
    assert config["forecast"]["target"] == "offered_calls"


def test_workforce_assumptions_are_valid_rates() -> None:
    config = load_config()
    workforce = config["workforce"]

    assert 0 < workforce["occupancy_target"] < 1
    assert 0 <= workforce["shrinkage_rate"] < 1
    assert workforce["rounding"] == "ceiling"


def test_service_level_rules_are_unambiguous() -> None:
    config = load_config()
    service_level = config["service_level"]

    assert 0 < service_level["target_rate"] <= 1
    assert service_level["answer_threshold_seconds"] > 0
    assert service_level["short_abandon_threshold_seconds"] >= 0


def test_weekly_seasonality_matches_interval_size() -> None:
    config = load_config()
    intervals_per_week = 7 * 24 * 60 // config["scope"]["interval_minutes"]

    assert config["forecast"]["weekly_seasonality_intervals"] == intervals_per_week
