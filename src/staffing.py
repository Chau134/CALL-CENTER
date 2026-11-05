"""Pure workload-based staffing calculations for 30-minute WFM intervals."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class StaffingRequirement:
    workload_hours: float
    required_productive_agents: int
    required_scheduled_agents: int


def calculate_staffing_requirement(
    volume: float,
    aht_seconds: float,
    interval_minutes: int,
    occupancy_target: float,
    shrinkage_rate: float,
) -> StaffingRequirement:
    """Return capacity-based requirement; this is not an Erlang C calculation."""
    if volume < 0:
        raise ValueError("volume must be non-negative")
    if aht_seconds < 0:
        raise ValueError("aht_seconds must be non-negative")
    if interval_minutes <= 0:
        raise ValueError("interval_minutes must be positive")
    if not 0 < occupancy_target <= 1:
        raise ValueError("occupancy_target must be in (0, 1]")
    if not 0 <= shrinkage_rate < 1:
        raise ValueError("shrinkage_rate must be in [0, 1)")

    workload_hours = volume * aht_seconds / 3600
    interval_hours = interval_minutes / 60
    productive = math.ceil(workload_hours / (interval_hours * occupancy_target))
    scheduled = math.ceil(productive / (1 - shrinkage_rate))
    return StaffingRequirement(
        workload_hours=round(workload_hours, 6),
        required_productive_agents=productive,
        required_scheduled_agents=scheduled,
    )


def requirement_as_dict(requirement: StaffingRequirement) -> dict[str, float | int]:
    return asdict(requirement)
