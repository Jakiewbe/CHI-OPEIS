from __future__ import annotations

from opeis_master.core.service import ScriptGenerationService


def build_raw(**overrides):
    data = {
        "basic.scenario": "time_sampling",
        "basic.project_name": "CFx demo",
        "basic.output_prefix": "CFXA",
        "basic.output_directory": "",
        "basic.file_override": True,
        "battery.chemistry": "CFx 半电池",
        "battery.capacity_ah": 1.0,
        "battery.nominal_voltage_v": 3.0,
        "battery.ocv_v": 3.0,
        "battery.upper_limit_v": 3.0,
        "battery.lower_limit_v": 1.5,
        "battery.cell_id": "",
        "strategy.fixed_voltage.target_points": "",
        "strategy.fixed_voltage.discharge_current_a": 0.0000865,
        "strategy.fixed_voltage.settle_seconds": 0.0,
        "strategy.fixed_voltage.sample_interval_s": 1.0,
        "strategy.time_sampling.cumulative_minutes": "2, 6, 10",
        "strategy.time_sampling.discharge_current_a": 0.0000865,
        "strategy.time_sampling.segment_delay_seconds": 0.0,
        "strategy.time_sampling.sample_interval_s": 1.0,
        "strategy.pulse_sequence.baseline_current_a": 0.0000865,
        "strategy.pulse_sequence.baseline_seconds": 60.0,
        "strategy.pulse_sequence.pulse_current_a": 0.001,
        "strategy.pulse_sequence.pulse_duration_seconds": 5.0,
        "strategy.pulse_sequence.rest_duration_seconds": 0.0,
        "strategy.pulse_sequence.repeat_count": 1,
        "strategy.pulse_sequence.sample_interval_s": 1.0,
        "impedance.use_ocv_init_e": True,
        "impedance.init_e_v": 3.0,
        "impedance.frequency_high_hz": 100000.0,
        "impedance.frequency_low_hz": 0.01,
        "impedance.amplitude_v": 0.005,
        "impedance.quiet_time_seconds": 2.0,
        "impedance.auto_sens": True,
        "impedance.impft": True,
    }
    data.update(overrides)
    return data


def test_time_sampling_warns_about_interrupted_discharge() -> None:
    result = ScriptGenerationService().preview(build_raw())

    assert result.can_generate is True
    assert any("EIS 时间不计入累计放电时间" in issue.message for issue in result.warnings)
    assert any("带中断的间歇放电曲线" in issue.message for issue in result.warnings)


def test_fixed_voltage_requires_descending_points() -> None:
    result = ScriptGenerationService().preview(
        build_raw(
            **{
                "basic.scenario": "fixed_voltage",
                "strategy.fixed_voltage.target_points": "2.4, 2.5",
                "strategy.time_sampling.cumulative_minutes": "",
            }
        )
    )

    assert result.can_generate is False
    assert any(issue.field == "strategy.fixed_voltage.target_points" for issue in result.errors)


def test_dense_low_frequency_warning_is_exposed() -> None:
    result = ScriptGenerationService().preview(
        build_raw(
            **{
                "basic.scenario": "fixed_voltage",
                "strategy.fixed_voltage.target_points": "2.9,2.8,2.7,2.6,2.5,2.4",
                "strategy.time_sampling.cumulative_minutes": "",
            }
        )
    )

    assert any(issue.field == "impedance.frequency_low_hz" for issue in result.warnings)


def test_invalid_number_list_returns_parse_error() -> None:
    result = ScriptGenerationService().preview(
        build_raw(**{"strategy.time_sampling.cumulative_minutes": "2, x, 10"})
    )

    assert result.can_generate is False
    assert any("无法解析数值" in issue.message for issue in result.errors)
