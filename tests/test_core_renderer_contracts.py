from __future__ import annotations

from pathlib import Path

from chi_generator.domain.models import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    ExperimentSequenceRequest,
    ImpedanceConfig,
    ProjectConfig,
    SamplingConfig,
    VoltagePointConfig,
    VoltagePointPhase,
    VoltageWindowConfig,
)
from chi_generator.domain.service import ScriptGenerationService


def _request(**overrides) -> ExperimentSequenceRequest:
    data = {
        "project": ProjectConfig(
            scheme_name="CFx demo",
            file_prefix="CFXA",
            export_dir=Path("C:/CHI/CFX_EIS"),
        ),
        "battery": BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        "current_basis": CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        "impedance_defaults": ImpedanceConfig(
            use_open_circuit_init_e=True,
            high_frequency_hz=100000.0,
            low_frequency_hz=0.01,
            amplitude_v=0.005,
            quiet_time_s=2.0,
        ),
        "phases": [
            VoltagePointPhase(
                label="Voltage step",
                voltage_window=VoltageWindowConfig(upper_v=3.2, lower_v=1.5),
                sampling=SamplingConfig(pre_wait_s=120.0, sample_interval_s=0.001),
                voltage_points=VoltagePointConfig(start_v=2.7, end_v=2.5, step_v=0.2),
            )
        ],
    }
    data.update(overrides)
    return ExperimentSequenceRequest.model_validate(data)


def test_common_header_footer_and_default_ocv_measurement_are_present() -> None:
    bundle = ScriptGenerationService().generate(_request())
    lines = bundle.minimal_script.splitlines()

    assert lines[:3] == ["fileoverride", r"folder=C:\CHI\CFX_EIS", "cellon"]
    assert lines[-2:] == ["celloff", "end"]
    assert "tech=imp" in lines
    assert "eio" in lines[:10]
    assert "save=CFXA_EIS_OCV" in lines
    assert "delay=120" in lines


def test_rendered_script_uses_blank_lines_to_separate_sections() -> None:
    bundle = ScriptGenerationService().generate(_request())
    lines = bundle.minimal_script.splitlines()

    assert lines[3] == ""
    assert "" in lines[-4:]


def test_rendered_names_include_stage_tokens_for_sequence_steps() -> None:
    bundle = ScriptGenerationService().generate(_request())

    assert "save=CFXA_S01_CC_2.70V" in bundle.minimal_script
    assert "save=CFXA_S01_EIS_2.70V" in bundle.minimal_script
    assert "save=CFXA_S01_CC_2.50V" in bundle.minimal_script
    assert "save=CFXA_S01_EIS_2.50V" in bundle.minimal_script
