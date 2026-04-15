from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from chi_generator.domain import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    CurrentInputMode,
    CurrentSetpointConfig,
    ExperimentSequenceRequest,
    ImpedanceConfig,
    ProcessDirection,
    ProjectConfig,
    RiskLevel,
    SamplingConfig,
    SamplingMode,
    TimeBasisMode,
    TimePointConfig,
    TimePointPhase,
    ValidationIssue,
    VoltagePointConfig,
    VoltagePointPhase,
    VoltageWindowConfig,
    validate_sequence_request,
)
from chi_generator.domain.calculations import calculate_ctc_recommendation
from chi_generator.ui.adapters import GuiBackend
from chi_generator.ui.models import CurrentBasisUiMode, GuiState
from chi_generator.ui.widgets import GuidedManualPointDialog


def test_dense_low_frequency_warning_uses_high_risk_level() -> None:
    request = ExperimentSequenceRequest(
        project=ProjectConfig(scheme_name="demo", file_prefix="demo", export_dir=Path.cwd()),
        battery=BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        impedance_defaults=ImpedanceConfig(low_frequency_hz=0.01),
        phases=[
            TimePointPhase(
                label="step1",
                direction=ProcessDirection.DISCHARGE,
                current_setpoint=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
                voltage_window=VoltageWindowConfig(upper_v=3.2, lower_v=1.5),
                sampling=SamplingConfig(pre_wait_s=0, sample_interval_s=0.001),
                insert_eis_after_each_point=True,
                time_points=TimePointConfig(
                    mode=SamplingMode.MANUAL,
                    manual_points_minutes=[10, 20, 30],
                    time_basis_mode=TimeBasisMode.ACTIVE_PROGRESS,
                ),
            )
        ],
    )

    result = validate_sequence_request(request)
    warning = next(issue for issue in result.warnings if issue.code == "dense_eis_low_frequency")
    assert warning.risk_level is RiskLevel.HIGH


def test_reference_current_basis_changes_preview_resolution() -> None:
    state = GuiState(
        current_basis_mode=CurrentBasisUiMode.REFERENCE,
        reference_current_a="0.002",
    )
    one_c_current_a, operating_current_a, operating_rate_c = GuiBackend().resolve_current_preview(state)

    assert one_c_current_a == 0.002
    assert operating_current_a == 0.0002
    assert operating_rate_c == 0.1


def test_manual_voltage_dialog_blocks_non_monotonic_points(qt_app: QApplication) -> None:
    dialog = GuidedManualPointDialog(
        title="编辑电压列表",
        text="3.2, 3.0, 3.1",
        is_voltage=True,
        direction=ProcessDirection.DISCHARGE,
    )
    try:
        ok_button = dialog.buttons.button(dialog.buttons.StandardButton.Ok)
        assert ok_button.isEnabled() is False
        assert "非单调电压点" in dialog.stats_label.text()
    finally:
        dialog.close()


def test_ctc_recommendation_keeps_margin_for_long_eis() -> None:
    interval_min, point_count = calculate_ctc_recommendation(120, 700)

    assert interval_min >= 19
    assert point_count == 6


def test_validation_issue_accepts_risk_level() -> None:
    issue = ValidationIssue(
        severity="warning",
        code="dense_eis_low_frequency",
        message="demo",
        risk_level=RiskLevel.HIGH,
    )
    assert issue.risk_level is RiskLevel.HIGH


def test_charge_voltage_checkpoints_warn_about_cp_target_usage() -> None:
    request = ExperimentSequenceRequest(
        project=ProjectConfig(scheme_name="demo", file_prefix="demo", export_dir=Path.cwd()),
        battery=BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        impedance_defaults=ImpedanceConfig(low_frequency_hz=0.1),
        phases=[
            VoltagePointPhase(
                label="charge-step",
                direction=ProcessDirection.CHARGE,
                current_setpoint=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
                voltage_window=VoltageWindowConfig(upper_v=3.2, lower_v=1.5),
                sampling=SamplingConfig(pre_wait_s=0, sample_interval_s=0.001),
                insert_eis_after_each_point=True,
                voltage_points=VoltagePointConfig(start_v=1.8, end_v=2.4, step_v=0.3),
            )
        ],
    )

    result = validate_sequence_request(request)

    warning = next(issue for issue in result.warnings if issue.code == "charge_cp_peis_transition")
    assert warning.risk_level is RiskLevel.HIGH
    assert "target voltage" in warning.message or "safety floor" in warning.hint
