from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtTest import QTest

from chi_generator.app import build_application
from chi_generator.ui.main_window import MainWindow
from chi_generator.ui.models import PhaseUiKind, WorkspaceMode
from chi_generator.ui.presets import PresetFileService
from chi_generator.ui.widgets import NoWheelComboBox


def test_export_directory_change_refreshes_script_preview(qt_app) -> None:
    app, window = build_application()
    try:
        new_export_dir = str(Path(r"C:\Users\chs\Desktop\OPEISMaster") / "chi-out")
        window.export_dir_edit.setText(new_export_dir)
        QTest.qWait(120)
        app.processEvents()

        script_text = window.output_panel.minimal_editor.toPlainText()
        expected_folder_line = f"folder={window.export_dir_edit.text()}".replace("/", "\\")
        assert expected_folder_line in script_text
    finally:
        window.close()


def test_time_workstep_refreshes_total_point_summary(qt_app) -> None:
    app, window = build_application()
    try:
        row = window.phase_editors[0]
        row.early_count_edit.setText("2")
        row.plateau_count_edit.setText("3")
        row.late_count_edit.setText("4")
        QTest.qWait(120)
        app.processEvents()

        assert "9" in row.point_count_label.text()
        assert window._last_bundle is not None
        assert window._last_bundle.total_point_count == 9
    finally:
        window.close()


def test_charge_voltage_workstep_uses_range_inputs(qt_app) -> None:
    app, window = build_application()
    try:
        row = window.phase_editors[0]
        row.phase_kind_combo.setCurrentIndex(row.phase_kind_combo.findData(PhaseUiKind.VOLTAGE_POINTS.value))
        row.direction_combo.setCurrentIndex(row.direction_combo.findData("charge"))
        row.voltage_start_edit.setText("2.8")
        row.voltage_end_edit.setText("3.2")
        row.voltage_step_edit.setText("0.2")
        QTest.qWait(120)
        app.processEvents()

        script_text = window.output_panel.minimal_editor.toPlainText()

        assert "3" in row.point_count_label.text()
        assert "ic=-0.0000865" in script_text
        assert "save=CHI_S01_CC_3.20V" in script_text
        assert window._last_bundle is not None
        assert window._last_bundle.phase_plans[0].effective_points == [2.8, 3.0, 3.2]
    finally:
        window.close()


def test_sampling_interval_presets_refresh_preview_for_workstep_and_pulse(qt_app) -> None:
    app, window = build_application()
    try:
        row = window.phase_editors[0]
        row.sample_interval_edit.setEditText("0.01")
        QTest.qWait(120)
        app.processEvents()
        assert "si=0.01" in window.output_panel.minimal_editor.toPlainText()

        window.mode_combo.setCurrentIndex(window.mode_combo.findData(WorkspaceMode.PULSE.value))
        window.pulse_sample_interval_edit.setEditText("0.005")
        QTest.qWait(120)
        app.processEvents()
        assert "si=0.005" in window.output_panel.minimal_editor.toPlainText()
    finally:
        window.close()


def test_time_compensation_mode_shows_manual_eis_input_and_summary(qt_app) -> None:
    app, window = build_application()
    try:
        row = window.phase_editors[0]
        row.time_basis_combo.setCurrentIndex(row.time_basis_combo.findData("interruption_compensated"))
        row.manual_eis_edit.setText("120")
        row.early_duration_edit.setText("10")
        row.early_count_edit.setText("3")
        row.plateau_duration_edit.setText("0")
        row.plateau_count_edit.setText("0")
        row.late_duration_edit.setText("0")
        row.late_count_edit.setText("0")
        window.show()
        QTest.qWait(120)
        app.processEvents()

        summary_text = window.output_panel.summary_label.text()
        script_text = window.output_panel.minimal_editor.toPlainText()

        assert not row.manual_eis_edit.isHidden()
        assert "2" in summary_text and "4" in summary_text
        assert any(token in script_text for token in ("st1=200", "st1=199.99998", "st1=200.00004"))
        assert any(token in script_text for token in ("st1=320", "st1=319.99998", "st1=320.00002", "st1=320.00004"))
    finally:
        window.close()


def test_time_workstep_exposes_advanced_voltage_safety_fields(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        row = window.phase_editors[0]

        assert row.phase_kind_combo.currentData() == PhaseUiKind.TIME_POINTS.value
        assert row.advanced_block.isVisible() is True
        assert row.upper_voltage_block.isVisible() is False
        assert row.lower_voltage_block.isVisible() is False

        row.advanced_toggle.click()
        QTest.qWait(80)
        app.processEvents()

        assert row.upper_voltage_block.isVisible() is True
        assert row.lower_voltage_block.isVisible() is True
    finally:
        window.close()


def test_workstep_editor_supports_add_move_and_delete(qt_app) -> None:
    app, window = build_application()
    try:
        window.add_voltage_phase_button.click()
        window.add_rest_phase_button.click()
        QTest.qWait(120)
        app.processEvents()

        assert len(window.phase_editors) == 3
        assert [row.collect_state().phase_kind.value for row in window.phase_editors] == ["time_points", "voltage_points", "rest"]

        window.phase_editors[2].move_up_button.click()
        QTest.qWait(120)
        app.processEvents()
        assert [row.collect_state().phase_kind.value for row in window.phase_editors] == ["time_points", "rest", "voltage_points"]

        window.phase_editors[1].delete_button.click()
        QTest.qWait(120)
        app.processEvents()
        assert [row.collect_state().phase_kind.value for row in window.phase_editors] == ["time_points", "voltage_points"]
    finally:
        window.close()


def test_workstep_switch_hides_unused_blocks_without_stray_widgets(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        row = window.phase_editors[0]

        row.phase_kind_combo.setCurrentIndex(row.phase_kind_combo.findData(PhaseUiKind.REST.value))
        QTest.qWait(80)
        app.processEvents()
        assert row.rest_duration_block.isVisible() is True
        assert row.time_basis_block.isVisible() is False
        assert row.voltage_start_block.isVisible() is False

        row.phase_kind_combo.setCurrentIndex(row.phase_kind_combo.findData(PhaseUiKind.TIME_POINTS.value))
        QTest.qWait(80)
        app.processEvents()
        assert row.rest_duration_block.isVisible() is False
        assert row.time_basis_block.isVisible() is True
        assert row.voltage_start_block.isVisible() is False
    finally:
        window.close()


def test_template_buttons_seed_expected_worksteps(qt_app) -> None:
    app, window = build_application()
    try:
        window.activation_template_button.click()
        QTest.qWait(120)
        app.processEvents()

        assert [row.collect_state().phase_kind.value for row in window.phase_editors] == ["time_points", "rest", "time_points"]
        assert [row.collect_state().direction.value for row in window.phase_editors if row.collect_state().phase_kind is not PhaseUiKind.REST] == [
            "charge",
            "discharge",
        ]
        assert window._last_bundle is not None
        assert window._last_bundle.total_point_count > 0
    finally:
        window.close()


def test_workspace_mode_switches_between_sequence_and_pulse_cards(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        assert window._scenario.currentData() == WorkspaceMode.SEQUENCE.value
        assert window.workstep_card.isVisible() is True
        assert window.pulse_card.isVisible() is False

        window.mode_combo.setCurrentIndex(window.mode_combo.findData(WorkspaceMode.PULSE.value))
        QTest.qWait(120)
        app.processEvents()
        assert window.workstep_card.isVisible() is False
        assert window.pulse_card.isVisible() is True
    finally:
        window.close()


def test_pulse_relaxation_fields_follow_selected_modes(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        window.mode_combo.setCurrentIndex(window.mode_combo.findData(WorkspaceMode.PULSE.value))
        QTest.qWait(80)
        app.processEvents()

        assert window.pulse_relaxation_current_mode_combo.isVisible() is False
        assert window.pulse_form.labelForField(window.pulse_relaxation_current_mode_combo).isVisible() is False
        assert window.pulse_rate_edit.isVisible() is True
        assert window.pulse_current_edit.isVisible() is False

        window.pulse_relaxation_mode_combo.setCurrentIndex(window.pulse_relaxation_mode_combo.findData("constant_current"))
        window.pulse_relaxation_current_mode_combo.setCurrentIndex(window.pulse_relaxation_current_mode_combo.findData("absolute"))
        window.pulse_current_mode_combo.setCurrentIndex(window.pulse_current_mode_combo.findData("absolute"))
        QTest.qWait(80)
        app.processEvents()

        assert window.pulse_relaxation_current_mode_combo.isVisible() is True
        assert window.pulse_form.labelForField(window.pulse_relaxation_current_mode_combo).isVisible() is True
        assert window.pulse_relaxation_rate_edit.isVisible() is False
        assert window.pulse_relaxation_current_edit.isVisible() is True
        assert window.pulse_rate_edit.isVisible() is False
        assert window.pulse_current_edit.isVisible() is True
    finally:
        window.close()


def test_preset_round_trip_restores_state(qt_app) -> None:
    recent_store = Path.cwd() / ".pytest-artifacts" / "recent_presets.json"
    preset_path = Path.cwd() / ".pytest-artifacts" / "workflow.chi-preset"
    recent_store.parent.mkdir(parents=True, exist_ok=True)

    window = MainWindow(preset_service=PresetFileService(recent_store_path=recent_store))
    try:
        row = window.phase_editors[0]
        row.label_edit.setText("实验工步")
        row.early_count_edit.setText("2")
        row.plateau_count_edit.setText("3")
        row.late_count_edit.setText("4")
        window.save_preset_to_path(preset_path)

        row.label_edit.setText("已改动")
        row.early_count_edit.setText("1")
        window.load_preset_from_path(preset_path)
        qt_app.processEvents()

        restored = window.phase_editors[0].collect_state()
        assert restored.label == "实验工步"
        assert restored.early_point_count == "2"
        assert restored.plateau_point_count == "3"
        assert restored.late_point_count == "4"
        assert window.recent_presets_combo.count() >= 1
    finally:
        window.close()


def test_no_wheel_combo_box_ignores_wheel_events(qt_app) -> None:
    combo = NoWheelComboBox()
    combo.addItems(["A", "B", "C"])
    combo.setCurrentIndex(0)

    event = QWheelEvent(
        QPointF(4.0, 4.0),
        QPointF(4.0, 4.0),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    combo.wheelEvent(event)

    assert combo.currentIndex() == 0
    assert not event.isAccepted()
