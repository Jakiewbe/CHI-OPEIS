"""Pure calculation helpers for the CHI domain layer."""

from __future__ import annotations

from math import log10

from .models import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    CurrentInputMode,
    CurrentResolution,
    CurrentSetpointConfig,
    ImpedanceConfig,
    PointPlan,
    ProcessDirection,
    PulseCurrentConfig,
    SamplingMode,
    SocTracePoint,
    SpacingMode,
    SuggestedPlan,
    TimeBasisMode,
    TimePointConfig,
    TimeSegmentConfig,
    VoltagePointConfig,
)


IMPFT_BASELINE_S = 700.0


def _round_values(values: list[float]) -> list[float]:
    return [round(value, 6) for value in values]


def _round_scalar(value: float) -> float:
    return round(value, 6)


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


def capacity_compensate_time_points(points: list[float], manual_eis_duration_s: float) -> tuple[list[float], list[float]]:
    compensation_min = manual_eis_duration_s / 60.0
    if compensation_min <= 0:
        return list(points), [0.0] * len(points)

    source_deltas = cumulative_timepoints_to_deltas(points)
    adjusted_deltas: list[float] = []
    actual_points: list[float] = []
    offsets: list[float] = []
    elapsed = 0.0
    source_elapsed = 0.0

    for delta in source_deltas:
        adjusted_delta = round(delta - compensation_min, 6)
        if adjusted_delta <= 0:
            raise ValueError(
                f"capacity compensation exceeds the point interval ({delta:g} min); increase the interval above {compensation_min:g} min"
            )
        adjusted_deltas.append(adjusted_delta)
        elapsed = round(elapsed + adjusted_delta, 6)
        source_elapsed = round(source_elapsed + delta, 6)
        actual_points.append(elapsed)
        offsets.append(round(elapsed - source_elapsed, 6))

    return actual_points, offsets


def _distribution_fractions(point_count: int, spacing_mode: SpacingMode) -> list[float]:
    if point_count <= 0:
        return []
    if point_count == 1:
        return [1.0]
    if spacing_mode is SpacingMode.LOG:
        base = 10.0
        return [((base ** (index / point_count)) - 1.0) / (base - 1.0) for index in range(1, point_count + 1)]
    if spacing_mode is SpacingMode.SQRT:
        return [(index / point_count) ** 2 for index in range(1, point_count + 1)]
    return [index / point_count for index in range(1, point_count + 1)]


def expand_voltage_range(config: VoltagePointConfig, direction: ProcessDirection) -> list[float]:
    if config.spacing_mode is SpacingMode.MANUAL:
        points = _round_values(list(config.manual_points_v))
        if any(current == previous for previous, current in zip(points, points[1:])):
            raise ValueError("manual voltage points must not contain duplicates")
        ascending = all(current > previous for previous, current in zip(points, points[1:]))
        descending = all(current < previous for previous, current in zip(points, points[1:]))
        if not ascending and not descending:
            raise ValueError("manual voltage points must be strictly monotonic")
        if direction is ProcessDirection.DISCHARGE and ascending:
            points.reverse()
        if direction is ProcessDirection.CHARGE and descending:
            points.reverse()
        if direction is ProcessDirection.DISCHARGE and any(current >= previous for previous, current in zip(points, points[1:])):
            raise ValueError("discharge voltage points must be strictly descending")
        if direction is ProcessDirection.CHARGE and any(current <= previous for previous, current in zip(points, points[1:])):
            raise ValueError("charge voltage points must be strictly ascending")
        return _round_values(points)

    start_v = round(config.start_v, 6)
    end_v = round(config.end_v, 6)
    step_v = round(config.step_v, 6)
    delta_v = round(abs(start_v - end_v), 6)
    if direction is ProcessDirection.DISCHARGE:
        if start_v <= end_v:
            raise ValueError("discharge voltage phases require start_v > end_v")
        sign = -1.0
    else:
        if start_v >= end_v:
            raise ValueError("charge voltage phases require start_v < end_v")
        sign = 1.0

    if config.spacing_mode is SpacingMode.LINEAR:
        points = [start_v]
        current = start_v
        while True:
            next_value = round(current + sign * step_v, 6)
            if (sign < 0 and next_value <= end_v) or (sign > 0 and next_value >= end_v):
                break
            points.append(next_value)
            current = next_value
        if abs(points[-1] - end_v) > 1e-6:
            points.append(end_v)
        return _round_values(points)

    point_count = int(round(delta_v / step_v)) + 1
    fractions = _distribution_fractions(point_count - 1, config.spacing_mode)
    points = [start_v]
    if fractions:
        points.extend(start_v + sign * delta_v * fraction for fraction in fractions)
    return _round_values(points)


def _segment_points(segment: TimeSegmentConfig, offset_minutes: float) -> list[float]:
    if segment.point_count == 0:
        return []
    if segment.duration_minutes <= 0:
        raise ValueError("segment duration must be > 0 when point_count > 0")
    step = segment.duration_minutes / segment.point_count
    return _round_values([offset_minutes + step * index for index in range(1, segment.point_count + 1)])


def _expand_fixed_time_points(config: TimePointConfig) -> list[float]:
    assert config.total_duration_minutes is not None
    if config.fixed_interval_minutes is not None:
        interval = config.fixed_interval_minutes
        points: list[float] = []
        value = interval
        while value <= config.total_duration_minutes + 1e-9:
            points.append(value)
            value += interval
        return _round_values(points)
    assert config.fixed_point_count is not None
    step = config.total_duration_minutes / config.fixed_point_count
    return _round_values([step * index for index in range(1, config.fixed_point_count + 1)])


def expand_time_segments(config: TimePointConfig) -> list[float]:
    if config.mode is SamplingMode.MANUAL:
        return _round_values(list(config.manual_points_minutes))
    if config.mode is SamplingMode.FIXED:
        return _expand_fixed_time_points(config)
    points: list[float] = []
    offset = 0.0
    for segment in config.segments:
        points.extend(_segment_points(segment, offset))
        offset += segment.duration_minutes
    if any(current <= previous for previous, current in zip(points, points[1:])):
        raise ValueError("time points must be strictly increasing")
    return points


def plan_voltage_points(config: VoltagePointConfig, *, direction: ProcessDirection = ProcessDirection.DISCHARGE) -> PointPlan:
    points = expand_voltage_range(config, direction)
    return PointPlan(points=points, actual_points=list(points))


def estimate_eis_scan_duration_s(config: ImpedanceConfig) -> float:
    """Refined duration model for CHI IMPFT/EIS scans."""
    decades = log10(config.high_frequency_hz / config.low_frequency_hz)
    point_count = max(2, int(round(decades * config.points_per_decade)) + 1)
    ratio = 10 ** (decades / (point_count - 1))
    frequencies = [config.high_frequency_hz / (ratio**index) for index in range(point_count)]
    sum_1_f = sum(1.0 / f for f in frequencies)
    cycles = 2.5
    scan_time = cycles * sum_1_f
    overhead = point_count * 0.1
    total_duration = _round_scalar((config.quiet_time_s + scan_time + overhead) * 1.1)
    return max(total_duration, 5.0)


def estimate_capacity_loss_mah(current_a: float, duration_s: float) -> float:
    return (abs(current_a) * duration_s) / 3600.0


def resolve_eis_duration_s(config: TimePointConfig, impedance: ImpedanceConfig | None = None) -> float:
    if config.manual_eis_duration_s is not None:
        return _round_scalar(config.manual_eis_duration_s)
    if config.estimated_eis_duration_s is not None:
        return _round_scalar(config.estimated_eis_duration_s)
    if impedance is None:
        return 0.0
    return estimate_eis_scan_duration_s(impedance)


def plan_time_points(
    config: TimePointConfig,
    *,
    impedance: ImpedanceConfig | None = None,
    include_interruptions: bool = True,
) -> PointPlan:
    points = expand_time_segments(config)
    actual_points = list(points)
    offsets = [0.0] * len(points)
    eis_duration_s = 0.0
    if config.time_basis_mode is TimeBasisMode.INTERRUPTION_COMPENSATED:
        eis_duration_s = resolve_eis_duration_s(config, impedance)
        if include_interruptions and eis_duration_s > 0:
            actual_points, offsets = compensate_time_points(points, eis_duration_s)
    elif config.time_basis_mode is TimeBasisMode.CAPACITY_COMPENSATED:
        eis_duration_s = resolve_eis_duration_s(config, impedance)
        if include_interruptions and eis_duration_s > 0:
            actual_points, offsets = capacity_compensate_time_points(points, eis_duration_s)
    deltas = cumulative_timepoints_to_deltas(actual_points)
    return PointPlan(
        points=points,
        deltas=deltas,
        actual_points=actual_points,
        compensation_offsets=offsets,
        eis_duration_s=eis_duration_s,
    )


def clamp_soc_percent(value: float) -> float:
    return max(0.0, min(100.0, round(value, 4)))


def simulate_soc_trace(
    *,
    capacity_ah: float,
    steps: list[tuple[float, float]],
    initial_soc_percent: float = 100.0,
) -> tuple[list[SocTracePoint], float | None]:
    if capacity_ah <= 0:
        return [SocTracePoint(time_s=0.0, soc_percent=initial_soc_percent)], None

    trace = [SocTracePoint(time_s=0.0, soc_percent=clamp_soc_percent(initial_soc_percent))]
    remaining_ah = capacity_ah * (initial_soc_percent / 100.0)
    zero_time_s: float | None = None
    elapsed_s = 0.0

    for duration_s, signed_current_a in steps:
        duration_s = max(duration_s, 0.0)
        if duration_s == 0:
            continue
        start_remaining_ah = remaining_ah
        delta_ah = (signed_current_a * duration_s) / 3600.0
        remaining_ah = max(0.0, min(capacity_ah, remaining_ah - delta_ah))
        if zero_time_s is None and signed_current_a > 0 and remaining_ah <= 0 < start_remaining_ah:
            discharge_ah = signed_current_a * duration_s / 3600.0
            zero_time_s = elapsed_s + (duration_s * (start_remaining_ah / discharge_ah))
        elapsed_s += duration_s
        trace.append(SocTracePoint(time_s=round(elapsed_s, 6), soc_percent=clamp_soc_percent((remaining_ah / capacity_ah) * 100.0)))

    return trace, zero_time_s


def suggest_voltage_plans(config: BatteryConfig) -> list[SuggestedPlan]:
    del config
    return [
        SuggestedPlan(
            label="Standard Range (3.2V - 1.5V, 0.1V Step)",
            point_count=18,
            points=[round(3.2 - 0.1 * i, 2) for i in range(18)],
            priority=1.0,
        ),
        SuggestedPlan(
            label="High Precision (0.05V Step)",
            point_count=35,
            points=[round(3.2 - 0.05 * i, 2) for i in range(35)],
            priority=0.8,
        ),
    ]


def suggest_time_plans(config: BatteryConfig) -> list[SuggestedPlan]:
    del config
    return [
        SuggestedPlan(
            label="CFx 24-point discharge",
            point_count=24,
            points=[1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 22, 27, 33, 40, 48, 57, 67, 78, 90, 103, 117, 132, 148],
            priority=1.0,
        ),
        SuggestedPlan(
            label="0.1C / 360 min / 10 EIS",
            point_count=10,
            points=_round_values([(360.0 / 10) * index for index in range(1, 11)]),
            priority=0.8,
        ),
    ]


def calculate_ctc_recommendation(total_duration_minutes: float, eis_duration_s: float) -> tuple[float, int]:
    eis_duration_min = max(eis_duration_s / 60.0, 0.0)
    # Keep some uninterrupted galvanostatic time between EIS scans instead of
    # packing points as tightly as possible.
    min_interval_min = max(eis_duration_min + 0.5, eis_duration_min / 0.6 if eis_duration_min > 0 else 5.0, 5.0)
    min_interval_min = _round_scalar(min_interval_min)
    if total_duration_minutes <= min_interval_min:
        return min_interval_min, 1
    max_point_count = max(1, int(total_duration_minutes / min_interval_min))
    preferred_counts = [12, 10, 8, 6, 5, 4, 3, 2, 1]
    point_count = next((count for count in preferred_counts if count <= max_point_count), max_point_count)
    nicer_interval = _round_scalar(total_duration_minutes / point_count)
    if nicer_interval < min_interval_min:
        point_count = max_point_count
        nicer_interval = _round_scalar(total_duration_minutes / point_count)
    return nicer_interval, point_count


__all__ = [
    "IMPFT_BASELINE_S",
    "SuggestedPlan",
    "apply_direction",
    "calculate_ctc_recommendation",
    "capacity_compensate_time_points",
    "clamp_soc_percent",
    "compensate_time_points",
    "cumulative_timepoints_to_deltas",
    "estimate_eis_scan_duration_s",
    "expand_time_segments",
    "expand_voltage_range",
    "plan_time_points",
    "plan_voltage_points",
    "resolve_current",
    "resolve_eis_duration_s",
    "resolve_one_c_current",
    "resolve_pulse_current",
    "simulate_soc_trace",
    "suggest_time_plans",
    "suggest_voltage_plans",
]
