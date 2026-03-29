from __future__ import annotations

from chi_generator.domain.calculations import expand_time_segments, expand_voltage_range
from chi_generator.domain.models import ProcessDirection, TimePointConfig, TimeSegmentConfig, VoltagePointConfig


def test_fixed_time_segments_expand_to_strictly_increasing_points() -> None:
    points = expand_time_segments(
        TimePointConfig(
            early=TimeSegmentConfig(duration_minutes=20.0, point_count=5),
            plateau=TimeSegmentConfig(duration_minutes=70.0, point_count=14),
            late=TimeSegmentConfig(duration_minutes=30.0, point_count=5),
        )
    )

    assert len(points) == 24
    assert points[0] == 4.0
    assert points[4] == 20.0
    assert points[-1] == 120.0
    assert all(previous < current for previous, current in zip(points, points[1:]))


def test_fixed_voltage_range_expands_for_discharge() -> None:
    points = expand_voltage_range(
        VoltagePointConfig(start_v=3.2, end_v=2.6, step_v=0.1),
        ProcessDirection.DISCHARGE,
    )

    assert points == [3.2, 3.1, 3.0, 2.9, 2.8, 2.7, 2.6]


def test_fixed_voltage_range_expands_for_charge() -> None:
    points = expand_voltage_range(
        VoltagePointConfig(start_v=2.6, end_v=3.2, step_v=0.1),
        ProcessDirection.CHARGE,
    )

    assert points == [2.6, 2.7, 2.8, 2.9, 3.0, 3.1, 3.2]
