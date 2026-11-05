import pytest

from src.staffing import calculate_staffing_requirement


def test_reference_staffing_example() -> None:
    result = calculate_staffing_requirement(45, 360, 30, 0.85, 0.30)

    assert result.workload_hours == 4.5
    assert result.required_productive_agents == 11
    assert result.required_scheduled_agents == 16


def test_zero_volume_requires_zero_agents() -> None:
    result = calculate_staffing_requirement(0, 360, 30, 0.85, 0.30)

    assert result.workload_hours == 0
    assert result.required_productive_agents == 0
    assert result.required_scheduled_agents == 0


def test_zero_shrinkage_does_not_gross_up_requirement() -> None:
    result = calculate_staffing_requirement(10, 180, 30, 0.80, 0)

    assert result.required_scheduled_agents == result.required_productive_agents


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((-1, 180, 30, 0.85, 0.3), "volume"),
        ((1, -1, 30, 0.85, 0.3), "aht_seconds"),
        ((1, 180, 0, 0.85, 0.3), "interval_minutes"),
        ((1, 180, 30, 0, 0.3), "occupancy_target"),
        ((1, 180, 30, 0.85, 1), "shrinkage_rate"),
    ],
)
def test_invalid_inputs_are_rejected(args: tuple, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_staffing_requirement(*args)
