from __future__ import annotations

import pytest

from chi_generator.ui.planning import format_point_list, plan_time_points, plan_voltage_points, resolve_current


def test_planning_converts_mAh_per_g_input_to_one_c_and_operating_current() -> None:
    result = resolve_current(
        active_mass_mg=1.0,
        theoretical_capacity_mah_mg=865.0,
        mode="rate",
        rate_c=0.1,
        current_a=0.0,
    )

    assert result.one_c_current_a == pytest.approx(0.000865)
    assert result.discharge_current_a == pytest.approx(0.0000865)
    assert result.discharge_rate_c == pytest.approx(0.1)


def test_planning_formats_smart_preset_points_for_summary() -> None:
    voltage_points = plan_voltage_points(
        initial_ocv_v=3.2,
        plateau_v=2.6,
        cutoff_v=1.5,
        point_count=8,
    )
    time_points = plan_time_points(
        total_s=120.0,
        early_s=20.0,
        platform_s=70.0,
        late_s=30.0,
        point_count=8,
    )

    assert voltage_points == pytest.approx([3.0, 2.8, 2.6, 2.38, 2.16, 1.94, 1.72, 1.5])
    assert time_points == pytest.approx([10.0, 20.0, 37.5, 55.0, 72.5, 90.0, 105.0, 120.0])
    assert format_point_list(voltage_points) == "3, 2.8, 2.6, 2.38, 2.16, 1.94, 1.72, 1.5"
    assert format_point_list(time_points) == "10, 20, 37.5, 55, 72.5, 90, 105, 120"
    assert voltage_points[0] < 3.2
    assert voltage_points[2] == pytest.approx(2.6)
    assert voltage_points[0] - voltage_points[1] == pytest.approx(voltage_points[1] - voltage_points[2])
    assert voltage_points[3] - voltage_points[4] == pytest.approx(voltage_points[4] - voltage_points[5])
    assert time_points[0] == pytest.approx(10.0)
    assert time_points[-1] == pytest.approx(120.0)
    assert time_points[2] - time_points[1] == pytest.approx(time_points[3] - time_points[2])
    assert time_points[6] - time_points[5] == pytest.approx(time_points[7] - time_points[6])
