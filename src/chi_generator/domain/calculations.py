"""Pure calculation helpers for the CHI domain layer."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from .models import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    CurrentInputMode,
    CurrentResolution,
    CurrentSetpointConfig,
    PointPlan,
    ProcessDirection,
    PulseCurrentConfig,
    TimeBasisMode,
    TimePointConfig,
    TimeSegmentConfig,
    VoltagePointConfig,
)


@dataclass(frozen=True)
class SuggestedPlan:
    point_count: int
    label: str
    points: list[float]
    priority: float = 0.0


def _round_values(values: list[float]) -> list[float]:
    return [round(value, 6) for value in values]


def _is_multiple(value: float, base: float, *, tolerance: float = 1e-6) -> bool:
    if base <= 0:
        return False
    quotient = value / base
    return abs(quotient - round(quotient)) <= tolerance


def resolve_one_c_current(battery: BatteryConfig, basis: CurrentBasisConfig) -> float:
    if basis.mode is CurrentBasisMode.REFERENCE:
        assert basis.reference_current_a is not None
        assert basis.reference_rate_c is not None
        return basis.reference_current_a / basis.reference_rate_c
    capacity_mah = (battery.active_material_mg / 1000.0) * battery.theoretical_capacity_mah_mg
    return capacity_mah / 1000.0


def resolve_current(battery: BatteryConfig, basis: CurrentBasisConfig, setpoint: CurrentSetpointConfig) -> CurrentResolution:
    one_c_current_a = resolve_one_c_current(battery, basis)
    if setpoint.mode is CurrentInputMode.RATE:
        assert setpoint.rate_c is not None
        current_a = one_c_current_a * setpoint.rate_c
        return CurrentResolution(one_c_current_a=one_c_current_a, operating_current_a=current_a, operating_rate_c=setpoint.rate_c)

    assert setpoint.current_a is not None
    return CurrentResolution(
        one_c_current_a=one_c_current_a,
        operating_current_a=setpoint.current_a,
        operating_rate_c=setpoint.current_a / one_c_current_a,
    )


def resolve_pulse_current(battery: BatteryConfig, basis: CurrentBasisConfig, current: PulseCurrentConfig) -> tuple[float, float]:
    one_c_current_a = resolve_one_c_current(battery, basis)
    if current.mode is CurrentInputMode.RATE:
        assert current.rate_c is not None
        return one_c_current_a * current.rate_c, current.rate_c
    assert current.current_a is not None
    return current.current_a, current.current_a / one_c_current_a


def apply_direction(current_a: float, direction: ProcessDirection) -> float:
    return current_a if direction is ProcessDirection.DISCHARGE else -current_a


def cumulative_timepoints_to_deltas(values: list[float], *, initial_time: float = 0.0) -> list[float]:
    previous = initial_time
    deltas: list[float] = []
    for value in values:
        if value <= previous:
            raise ValueError("time points must be strictly increasing")
        deltas.append(round(value - previous, 6))
        previous = value
    return deltas


def compensate_time_points(points: list[float], manual_eis_duration_s: float) -> tuple[list[float], list[float]]:
    compensation_min = manual_eis_duration_s / 60.0
    offsets = [round(index * compensation_min, 6) for index, _ in enumerate(points)]
    actual_points = [round(point + offset, 6) for point, offset in zip(points, offsets, strict=True)]
    return actual_points, offsets


def expand_voltage_range(config: VoltagePointConfig, direction: ProcessDirection) -> list[float]:
    start_v = round(config.start_v, 6)
    end_v = round(config.end_v, 6)
    step_v = round(config.step_v, 6)
    delta_v = round(abs(start_v - end_v), 6)
    if direction is ProcessDirection.DISCHARGE:
        if start_v <= end_v:
            raise ValueError("discharge voltage workstep requires start_v > end_v")
        sign = -1.0
    else:
        if start_v >= end_v:
            raise ValueError("charge voltage workstep requires start_v < end_v")
        sign = 1.0
    if not _is_multiple(delta_v, step_v):
        raise ValueError("voltage range must land exactly on the step grid so the endpoint is included")
    point_count = int(round(delta_v / step_v)) + 1
    return _round_values([start_v + sign * step_v * index for index in range(point_count)])


def _segment_points(segment: TimeSegmentConfig, offset_minutes: float) -> list[float]:
    if segment.point_count == 0:
        return []
    if segment.duration_minutes <= 0:
        raise ValueError("time segment duration must be greater than 0 when point_count > 0")
    step = segment.duration_minutes / segment.point_count
    return _round_values([offset_minutes + step * index for index in range(1, segment.point_count + 1)])


def expand_time_segments(config: TimePointConfig) -> list[float]:
    points = [
        *_segment_points(config.early, 0.0),
        *_segment_points(config.plateau, config.early.duration_minutes),
        *_segment_points(config.late, config.early.duration_minutes + config.plateau.duration_minutes),
    ]
    if any(current <= previous for previous, current in zip(points, points[1:])):
        raise ValueError("time points must be strictly increasing")
    return points


def plan_voltage_points(config: VoltagePointConfig, *, direction: ProcessDirection = ProcessDirection.DISCHARGE) -> PointPlan:
    points = expand_voltage_range(config, direction)
    return PointPlan(points=points, actual_points=list(points))


def plan_time_points(config: TimePointConfig) -> PointPlan:
    points = expand_time_segments(config)
    actual_points = list(points)
    offsets = [0.0] * len(points)
    if config.time_basis_mode is TimeBasisMode.INTERRUPTION_COMPENSATED:
        assert config.manual_eis_duration_s is not None
        actual_points, offsets = compensate_time_points(points, config.manual_eis_duration_s)
    deltas = cumulative_timepoints_to_deltas(actual_points)
    return PointPlan(points=points, deltas=deltas, actual_points=actual_points, compensation_offsets=offsets)


def suggest_voltage_plans(*_args, **_kwargs) -> list[SuggestedPlan]:
    return []


def suggest_time_plans(*_args, **_kwargs) -> list[SuggestedPlan]:
    return []


__all__ = [
    "SuggestedPlan",
    "apply_direction",
    "compensate_time_points",
    "cumulative_timepoints_to_deltas",
    "expand_time_segments",
    "expand_voltage_range",
    "plan_time_points",
    "plan_voltage_points",
    "resolve_current",
    "resolve_one_c_current",
    "resolve_pulse_current",
    "suggest_time_plans",
    "suggest_voltage_plans",
]
