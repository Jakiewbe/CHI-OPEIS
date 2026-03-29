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
        "strategy.time_sampling.cumulative_minutes": "2, 6",
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


def test_time_sampling_renders_istep_and_imp_blocks() -> None:
    result = ScriptGenerationService().generate(build_raw())

    assert result.can_generate is True
    assert "tech=istep" in result.script
    assert "st1=120" in result.script
    assert "st1=240" in result.script
    assert "save=CFXA_D002M" in result.script
    assert "save=CFXA_E006M" in result.script
    assert "eio" in result.script


def test_fixed_voltage_renders_cp_with_explicit_reset_params() -> None:
    result = ScriptGenerationService().generate(
        build_raw(
            **{
                "basic.scenario": "fixed_voltage",
                "strategy.fixed_voltage.target_points": "2.7, 2.5",
                "strategy.time_sampling.cumulative_minutes": "",
            }
        )
    )

    assert result.can_generate is True
    assert "tech=cp" in result.script
    assert "ia=0" in result.script
    assert "ta=0.05" in result.script
    assert "cl=1" in result.script
    assert "prioe" in result.script
    assert "ei=2.7" in result.script


def test_pulse_sequence_renders_unique_pre_and_post_impedance_files() -> None:
    result = ScriptGenerationService().generate(
        build_raw(**{"basic.scenario": "pulse_sequence"})
    )

    assert result.can_generate is True
    assert "save=CFXA_PRE01" in result.script
    assert "save=CFXA_POST01" in result.script
