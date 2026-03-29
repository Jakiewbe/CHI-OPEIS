"""Pure calculation helpers for the OPEIS domain layer."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from opeis_master.domain.contracts import CurrentInputConfig, NormalizedCurrent, TimeSegment, TimepointPlan
from opeis_master.domain.enums import CurrentInputMode
from opeis_master.domain.validation import ensure_positive, ensure_strictly_increasing


def calculate_one_c_current(*, current_a: float, rate_c: float) -> float:
    if current_a <= 0:
        raise ValueError("current_a must be positive.")
    if rate_c <= 0:
        raise ValueError("rate_c must be positive.")
    return current_a / rate_c


def current_for_rate(*, one_c_current_a: float, rate_c: float) -> float:
    if one_c_current_a <= 0:
        raise ValueError("one_c_current_a must be positive.")
    if rate_c <= 0:
        raise ValueError("rate_c must be positive.")
    return one_c_current_a * rate_c


def rate_for_current(*, one_c_current_a: float, current_a: float) -> float:
    if one_c_current_a <= 0:
        raise ValueError("one_c_current_a must be positive.")
    if current_a <= 0:
        raise ValueError("current_a must be positive.")
    return current_a / one_c_current_a


def normalize_current_input(config: CurrentInputConfig) -> NormalizedCurrent:
    if config.mode is CurrentInputMode.DIRECT_1C:
        assert config.one_c_current_a is not None
        return NormalizedCurrent(input_mode=config.mode, one_c_current_a=config.one_c_current_a)

    assert config.reference is not None
    return NormalizedCurrent(
        input_mode=config.mode,
        one_c_current_a=calculate_one_c_current(current_a=config.reference.current_a, rate_c=config.reference.rate_c),
        source_rate_c=config.reference.rate_c,
        source_current_a=config.reference.current_a,
    )


def expand_uniform_segment(segment: TimeSegment) -> list[float]:
    step = (segment.end - segment.start) / (segment.point_count - 1)
    timepoints = [segment.start + index * step for index in range(segment.point_count)]
    if not segment.include_start:
        timepoints = timepoints[1:]
    if not segment.include_end:
        timepoints = timepoints[:-1]
    return timepoints


def expand_timepoint_plan(plan: TimepointPlan) -> list[float]:
    cumulative_timepoints: list[float] = []
    for segment in plan.segments:
        cumulative_timepoints.extend(expand_uniform_segment(segment))
    ensure_strictly_increasing(cumulative_timepoints, name="timepoints")
    return cumulative_timepoints


def cumulative_timepoints_to_deltas(timepoints: Sequence[float], *, initial_time: float = 0.0) -> list[float]:
    if initial_time < 0:
        raise ValueError("initial_time must be non-negative.")

    materialized = list(timepoints)
    ensure_positive(materialized, name="timepoints")
    ensure_strictly_increasing(materialized, name="timepoints")
    if materialized and materialized[0] <= initial_time:
        raise ValueError("The first timepoint must be greater than initial_time.")

    deltas: list[float] = []
    previous = initial_time
    for timepoint in materialized:
        delta = timepoint - previous
        if delta <= 0:
            raise ValueError("All time deltas must be positive.")
        deltas.append(delta)
        previous = timepoint
    return deltas


def timepoint_plan_to_deltas(plan: TimepointPlan, *, initial_time: float = 0.0) -> list[float]:
    return cumulative_timepoints_to_deltas(expand_timepoint_plan(plan), initial_time=initial_time)


def timepoints_to_deltas(timepoints: Sequence[float], *, initial_time: float = 0.0) -> list[float]:
    return cumulative_timepoints_to_deltas(timepoints, initial_time=initial_time)


def convert_timepoints_to_seconds(plan: TimepointPlan, values: Iterable[float]) -> list[float]:
    return [plan.unit.to_seconds(value) for value in values]


__all__ = [
    "calculate_one_c_current",
    "convert_timepoints_to_seconds",
    "cumulative_timepoints_to_deltas",
    "current_for_rate",
    "expand_timepoint_plan",
    "expand_uniform_segment",
    "normalize_current_input",
    "rate_for_current",
    "timepoint_plan_to_deltas",
    "timepoints_to_deltas",
]
