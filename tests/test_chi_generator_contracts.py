from __future__ import annotations

from pathlib import Path

import pytest

from chi_generator.domain.models import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    CurrentInputMode,
    CurrentSetpointConfig,
    ExperimentRequest,
    ExperimentSequenceRequest,
    ImpedanceConfig,
    ImpedanceMeasurementMode,
    ProcessDirection,
    ProjectConfig,
    PulseConfig,
    PulseCurrentConfig,
    RelaxationMode,
    RestPhase,
    SamplingConfig,
    ScriptKind,
    SequenceScriptBundle,
    TimeBasisMode,
    TimePointConfig,
    TimePointPhase,
    TimeSegmentConfig,
    VoltagePointConfig,
    VoltagePointPhase,
    VoltageWindowConfig,
)
from chi_generator.domain.service import ScriptGenerationService


def _base_sequence_request(phases: list) -> ExperimentSequenceRequest:
    return ExperimentSequenceRequest(
        project=ProjectConfig(scheme_name="CHI demo", file_prefix="DEMO", export_dir=Path(".")),
        battery=BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        impedance_defaults=ImpedanceConfig(
            use_open_circuit_init_e=True,
            high_frequency_hz=100000.0,
            low_frequency_hz=0.01,
            amplitude_v=0.005,
            quiet_time_s=2.0,
        ),
        phases=phases,
    )


def _rate_setpoint(rate_c: float) -> CurrentSetpointConfig:
    return CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=rate_c)


def _voltage_window() -> VoltageWindowConfig:
    return VoltageWindowConfig(upper_v=3.2, lower_v=1.5)


def _time_config() -> TimePointConfig:
    return TimePointConfig(
        early=TimeSegmentConfig(duration_minutes=20.0, point_count=5),
        plateau=TimeSegmentConfig(duration_minutes=70.0, point_count=14),
        late=TimeSegmentConfig(duration_minutes=30.0, point_count=5),
    )


def test_voltage_range_generation_expands_points_and_renders_cp_blocks() -> None:
    bundle = ScriptGenerationService().generate(
        _base_sequence_request(
            [
                VoltagePointPhase(
                    label="Voltage phase",
                    direction=ProcessDirection.DISCHARGE,
                    current_setpoint=_rate_setpoint(0.1),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                    voltage_points=VoltagePointConfig(start_v=3.2, end_v=3.0, step_v=0.1),
                )
            ]
        )
    )

    assert isinstance(bundle, SequenceScriptBundle)
    assert bundle.can_generate is True
    assert bundle.total_point_count == 3
    assert bundle.total_eis_count == 4
    assert bundle.one_c_current_a == pytest.approx(0.000865)
    assert bundle.phase_plans[0].effective_points == pytest.approx([3.2, 3.1, 3.0])
    assert "eh=3.2\nel=3.2" in bundle.minimal_script
    assert "eh=3.2\nel=3.1" in bundle.minimal_script
    assert "tc=100000" in bundle.minimal_script
    assert "pn=n" in bundle.minimal_script
    assert "save=DEMO_S01_CC_3.20V" in bundle.minimal_script
    assert "save=DEMO_S01_EIS_3.00V" in bundle.minimal_script


def test_charge_voltage_range_renders_target_as_cp_upper_limit() -> None:
    bundle = ScriptGenerationService().generate(
        _base_sequence_request(
            [
                VoltagePointPhase(
                    label="Charge voltage",
                    direction=ProcessDirection.CHARGE,
                    current_setpoint=_rate_setpoint(0.1),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                    voltage_points=VoltagePointConfig(start_v=1.8, end_v=3.0, step_v=0.6),
                )
            ]
        )
    )

    assert bundle.can_generate is True
    assert bundle.phase_plans[0].effective_points == pytest.approx([1.8, 2.4, 3.0])
    assert "ic=-0.0000865" in bundle.minimal_script
    assert "eh=1.8\nel=1.5" in bundle.minimal_script
    assert "eh=2.4\nel=1.5" in bundle.minimal_script
    assert "eh=3\nel=1.5" in bundle.minimal_script


def test_time_segments_generate_expected_points_and_counts() -> None:
    bundle = ScriptGenerationService().generate(
        _base_sequence_request(
            [
                TimePointPhase(
                    label="Time phase",
                    direction=ProcessDirection.DISCHARGE,
                    current_setpoint=_rate_setpoint(0.1),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=123.0, sample_interval_s=0.001),
                    time_points=_time_config(),
                )
            ]
        )
    )

    assert bundle.can_generate is True
    assert bundle.phase_plans[0].point_count == 24
    assert bundle.phase_plans[0].effective_points[:8] == pytest.approx([4, 8, 12, 16, 20, 25, 30, 35])
    assert bundle.minimal_script.count("delay=123") == 24
    assert "save=DEMO_S01_CC_T4M" in bundle.minimal_script
    assert "save=DEMO_S01_EIS_T120M" in bundle.minimal_script


def test_charge_then_rest_then_discharge_render_independently() -> None:
    bundle = ScriptGenerationService().generate(
        _base_sequence_request(
            [
                TimePointPhase(
                    label="Charge",
                    direction=ProcessDirection.CHARGE,
                    current_setpoint=_rate_setpoint(0.05),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                    time_points=TimePointConfig(
                        early=TimeSegmentConfig(duration_minutes=10, point_count=2),
                        plateau=TimeSegmentConfig(duration_minutes=0, point_count=0),
                        late=TimeSegmentConfig(duration_minutes=0, point_count=0),
                    ),
                ),
                RestPhase(label="Rest", duration_s=30),
                VoltagePointPhase(
                    label="Discharge",
                    direction=ProcessDirection.DISCHARGE,
                    current_setpoint=_rate_setpoint(0.1),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                    voltage_points=VoltagePointConfig(start_v=3.2, end_v=3.0, step_v=0.1),
                ),
            ]
        )
    )

    assert bundle.can_generate is True
    assert len(bundle.phase_plans) == 3
    assert bundle.total_point_count == 5
    assert "is1=-0.00004325" in bundle.minimal_script
    assert "ic=0.0000865" in bundle.minimal_script
    assert "delay=30" in bundle.minimal_script
    assert "save=DEMO_S01_CC_T5M" in bundle.minimal_script
    assert "save=DEMO_S03_CC_3.20V" in bundle.minimal_script


def test_compensation_only_affects_current_time_step() -> None:
    bundle = ScriptGenerationService().generate(
        _base_sequence_request(
            [
                TimePointPhase(
                    label="Compensated",
                    direction=ProcessDirection.DISCHARGE,
                    current_setpoint=_rate_setpoint(0.1),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                    time_points=TimePointConfig(
                        early=TimeSegmentConfig(duration_minutes=10, point_count=3),
                        plateau=TimeSegmentConfig(duration_minutes=0, point_count=0),
                        late=TimeSegmentConfig(duration_minutes=0, point_count=0),
                        time_basis_mode=TimeBasisMode.INTERRUPTION_COMPENSATED,
                        manual_eis_duration_s=120,
                    ),
                ),
                TimePointPhase(
                    label="Plain",
                    direction=ProcessDirection.DISCHARGE,
                    current_setpoint=_rate_setpoint(0.1),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                    time_points=TimePointConfig(
                        early=TimeSegmentConfig(duration_minutes=10, point_count=2),
                        plateau=TimeSegmentConfig(duration_minutes=0, point_count=0),
                        late=TimeSegmentConfig(duration_minutes=0, point_count=0),
                    ),
                ),
            ]
        )
    )

    assert bundle.can_generate is True
    assert bundle.phase_plans[0].effective_points == pytest.approx([3.333333, 6.666667, 10.0])
    assert bundle.phase_plans[0].rendered_points == pytest.approx([3.333333, 8.666667, 14.0])
    assert bundle.phase_plans[1].rendered_points == pytest.approx([5.0, 10.0])
    assert "补偿偏移（min）： 0, 2, 4" in "\n".join(bundle.summary_lines)


def test_ctc_compensation_reduces_current_hold_to_preserve_equivalent_capacity() -> None:
    bundle = ScriptGenerationService().generate(
        _base_sequence_request(
            [
                TimePointPhase(
                    label="CTC",
                    direction=ProcessDirection.DISCHARGE,
                    current_setpoint=_rate_setpoint(0.1),
                    voltage_window=_voltage_window(),
                    sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                    time_points=TimePointConfig(
                        mode="manual",
                        manual_points_minutes=[60],
                        time_basis_mode=TimeBasisMode.CAPACITY_COMPENSATED,
                        manual_eis_duration_s=1200,
                    ),
                )
            ]
        )
    )

    assert bundle.can_generate is True
    assert bundle.phase_plans[0].effective_points == pytest.approx([60.0])
    assert bundle.phase_plans[0].rendered_points == pytest.approx([40.0])
    assert "st1=2400" in bundle.minimal_script
    assert "容量补偿偏移（min）： -20" in "\n".join(bundle.summary_lines)


def test_charge_voltage_range_requires_ascending_directional_range() -> None:
    request = _base_sequence_request(
        [
            VoltagePointPhase(
                label="Charge voltage",
                direction=ProcessDirection.CHARGE,
                current_setpoint=_rate_setpoint(0.1),
                voltage_window=_voltage_window(),
                sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
                voltage_points=VoltagePointConfig(start_v=3.2, end_v=3.0, step_v=0.1),
            )
        ]
    )

    bundle = ScriptGenerationService().generate(request)

    assert bundle.can_generate is False
    assert any("start_v < end_v" in issue.message for issue in bundle.issues)


def test_pulse_generation_still_supported() -> None:
    request = ExperimentRequest(
        kind=ScriptKind.PULSE,
        project=ProjectConfig(scheme_name="Pulse demo", file_prefix="PULSE", export_dir=Path(".")),
        battery=BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        discharge_current=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
        voltage_window=VoltageWindowConfig(upper_v=4.0, lower_v=-1.0),
        sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=0.001),
        impedance=ImpedanceConfig(
            use_open_circuit_init_e=True,
            high_frequency_hz=100000.0,
            low_frequency_hz=0.01,
            amplitude_v=0.005,
            quiet_time_s=2.0,
        ),
        pulse=PulseConfig(
            relaxation_mode=RelaxationMode.CONSTANT_CURRENT,
            relaxation_time_s=60.0,
            relaxation_current=PulseCurrentConfig(mode=CurrentInputMode.RATE, rate_c=0.02),
            pulse_current=PulseCurrentConfig(mode=CurrentInputMode.RATE, rate_c=1.0),
            pulse_duration_s=5.0,
            pulse_count=1,
            sample_interval_s=0.001,
        ),
    )

    bundle = ScriptGenerationService().generate(request)

    assert bundle.can_generate is True
    assert "save=PULSE_REL_01" in bundle.minimal_script
    assert "save=PULSE_PULSE_01" in bundle.minimal_script
    assert "el=-1" in bundle.minimal_script


def test_impedance_measurement_mode_renders_ft_or_sf() -> None:
    request = _base_sequence_request(
        [
            VoltagePointPhase(
                label="Voltage phase",
                direction=ProcessDirection.DISCHARGE,
                current_setpoint=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
                voltage_window=VoltageWindowConfig(upper_v=3.2, lower_v=1.5),
                sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=1.0),
                voltage_points=VoltagePointConfig(start_v=3.2, end_v=3.1, step_v=0.1),
            )
        ]
    )

    ft_bundle = ScriptGenerationService().generate(request)
    assert "impft" in ft_bundle.minimal_script
    assert "impsf" not in ft_bundle.minimal_script

    sf_request = request.model_copy(update={"impedance_defaults": request.impedance_defaults.model_copy(update={"measurement_mode": ImpedanceMeasurementMode.SF})})
    sf_bundle = ScriptGenerationService().generate(sf_request)
    assert "impsf" in sf_bundle.minimal_script
    assert "impft" not in sf_bundle.minimal_script


def test_legacy_fit_false_maps_to_impsf() -> None:
    config = ImpedanceConfig.model_validate({"fit": False, "use_open_circuit_init_e": True})

    assert config.measurement_mode is ImpedanceMeasurementMode.SF
    assert config.fit is False


def test_pulse_tail_voltage_phase_renders_after_all_pulses() -> None:
    request = ExperimentRequest(
        kind=ScriptKind.PULSE,
        project=ProjectConfig(scheme_name="Pulse tail", file_prefix="PTAIL", export_dir=Path(".")),
        battery=BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        discharge_current=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
        voltage_window=VoltageWindowConfig(upper_v=4.0, lower_v=-1.0),
        sampling=SamplingConfig(pre_wait_s=0.0, sample_interval_s=1.0),
        impedance=ImpedanceConfig(use_open_circuit_init_e=True, high_frequency_hz=100000.0, low_frequency_hz=0.01, amplitude_v=0.005, quiet_time_s=2.0),
        pulse=PulseConfig(
            relaxation_mode=RelaxationMode.REST,
            relaxation_time_s=60.0,
            pulse_current=PulseCurrentConfig(mode=CurrentInputMode.RATE, rate_c=1.0),
            pulse_duration_s=5.0,
            pulse_count=2,
            sample_interval_s=1.0,
            append_tail_voltage_phase=True,
            tail_current=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
            tail_voltage_points=VoltagePointConfig(start_v=3.2, end_v=3.0, step_v=0.1),
            tail_voltage_window=VoltageWindowConfig(upper_v=4.0, lower_v=-1.0),
            tail_sample_interval_s=1.0,
            tail_insert_eis_after_each_point=True,
        ),
    )

    bundle = ScriptGenerationService().generate(request)

    assert bundle.can_generate is True
    assert bundle.minimal_script.index("save=PTAIL_EIS_POST02") < bundle.minimal_script.index("save=PTAIL_TAIL_CC_3.20V")
    assert "save=PTAIL_TAIL_EIS_3.20V" in bundle.minimal_script
    save_lines = [line for line in bundle.minimal_script.splitlines() if line.startswith("save=")]
    assert len(save_lines) == len(set(save_lines))
