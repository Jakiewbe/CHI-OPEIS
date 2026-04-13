from __future__ import annotations

from pathlib import Path

from PySide6.QtTest import QTest

from chi_generator.app import build_application
from chi_generator.ui.main_window import MainWindow
from chi_generator.ui.models import PhaseUiKind, WorkspaceMode
from chi_generator.ui.presets import PresetFileService


def test_export_directory_change_refreshes_script_preview(qt_app) -> None:
    app, window = build_application()
    try:
        new_export_dir = str(Path(r"C:\Users\chs\Desktop\OPEISMaster") / "chi-out")
        window.export_dir_edit.setText(new_export_dir)
        QTest.qWait(120)
        app.processEvents()
        expected_folder_line = f"folder={window.export_dir_edit.text()}".replace("/", "\\")
        assert expected_folder_line in window.output_panel.minimal_editor.toPlainText()
    finally:
        window.close()


def test_segmented_time_workstep_refreshes_total_point_summary(qt_app) -> None:
    app, window = build_application()
    try:
        row = window.phase_editors[0]
        row.segment_editors[0].point_count_edit.setText("2")
        row.segment_editors[1].point_count_edit.setText("3")
        row.segment_editors[2].point_count_edit.setText("4")
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
        assert "3" in row.point_count_label.text()
        assert "ic=-0.0000865" in window.output_panel.minimal_editor.toPlainText()
        assert "save=CHI_S01_CC_3.20V" in window.output_panel.minimal_editor.toPlainText()
        assert window._last_bundle is not None
        assert window._last_bundle.phase_plans[0].effective_points == [2.8, 3.0, 3.2]
    finally:
        window.close()


def test_non_divisible_voltage_range_still_generates_preview(qt_app) -> None:
    app, window = build_application()
    try:
        row = window.phase_editors[0]
        row.phase_kind_combo.setCurrentIndex(row.phase_kind_combo.findData(PhaseUiKind.VOLTAGE_POINTS.value))
        row.voltage_start_edit.setText("3.2")
        row.voltage_end_edit.setText("2.55")
        row.voltage_step_edit.setText("0.1")
        QTest.qWait(120)
        app.processEvents()
        assert window._last_bundle is not None
        assert window._last_bundle.phase_plans[0].effective_points[-1] == 2.55
        assert "save=CHI_S01_CC_2.55V" in window.output_panel.minimal_editor.toPlainText()
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


def test_fixed_mode_supports_duration_and_count_planning(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        row = window.phase_editors[0]
        row.time_mode_combo.setCurrentIndex(row.time_mode_combo.findData("fixed"))
        row.fixed_mode_combo.setCurrentIndex(row.fixed_mode_combo.findData("point_count"))
        row.fixed_total_duration_edit.setText("360")
        row.fixed_point_count_edit.setText("10")
        QTest.qWait(120)
        app.processEvents()
        assert "10" in row.point_count_label.text()
        assert window._last_bundle is not None
        assert window._last_bundle.total_point_count == 10
    finally:
        window.close()


def test_manual_mode_and_compensation_summary_are_visible(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        row = window.phase_editors[0]
        row.time_mode_combo.setCurrentIndex(row.time_mode_combo.findData("manual"))
        row.time_basis_combo.setCurrentIndex(row.time_basis_combo.findData("interruption_compensated"))
        row.manual_eis_edit.setText("120")
        row._manual_time_points_text = "10, 20, 30"
        row._sync_visibility()
        row._handle_change()
        QTest.qWait(120)
        app.processEvents()
        assert "补偿偏移" in window.output_panel.summary_label.text()
    finally:
        window.close()


def test_smart_recommend_prefers_clean_fixed_interval_plan(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        row = window.phase_editors[0]
        row.time_mode_combo.setCurrentIndex(row.time_mode_combo.findData("fixed"))
        row.fixed_total_duration_edit.setText("120")
        row.manual_eis_edit.setText("700")
        row.smart_recommend_button.click()
        QTest.qWait(120)
        app.processEvents()
        assert row.fixed_mode_combo.currentData() == "interval"
        assert row.fixed_interval_edit.text() == "20"
        assert row.fixed_point_count_edit.text() == "6"
    finally:
        window.close()


def test_blank_workstep_name_falls_back_to_readable_default(qt_app) -> None:
    app, window = build_application()
    try:
        row = window.phase_editors[0]
        row.label_edit.setText("")
        row.direction_combo.setCurrentIndex(row.direction_combo.findData("discharge"))
        state = row.collect_state()
        assert state.label == "放电时间工步 1"
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


def test_selected_rows_can_be_wrapped_into_loop_block(qt_app) -> None:
    app, window = build_application()
    try:
        window.add_voltage_phase_button.click()
        QTest.qWait(120)
        app.processEvents()
        window.phase_editors[0].set_selected(True)
        window.phase_editors[1].set_selected(True)
        window.create_loop_button.click()
        QTest.qWait(120)
        app.processEvents()
        state = window._collect_state()
        assert len(state.workflow_items) == 1
        assert state.workflow_items[0].item_kind.value == "loop"
        assert len(state.phases) == 4
    finally:
        window.close()


def test_workstep_switches_between_segmented_voltage_and_rest_modes(qt_app) -> None:
    app, window = build_application()
    try:
        window.show()
        app.processEvents()
        row = window.phase_editors[0]
        assert row.segment_panel.isVisible() is True
        row.phase_kind_combo.setCurrentIndex(row.phase_kind_combo.findData(PhaseUiKind.REST.value))
        QTest.qWait(80)
        app.processEvents()
        assert row.rest_row.isVisible() is True
        assert row.segment_panel.isVisible() is False
        row.phase_kind_combo.setCurrentIndex(row.phase_kind_combo.findData(PhaseUiKind.VOLTAGE_POINTS.value))
        QTest.qWait(80)
        app.processEvents()
        assert row.voltage_row.isVisible() is True
        assert row.rest_row.isVisible() is False
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
        assert window.pulse_relaxation_rate_edit.isVisible() is False
        assert window.pulse_relaxation_current_edit.isVisible() is True
        assert window.pulse_rate_edit.isVisible() is False
        assert window.pulse_current_edit.isVisible() is True
    finally:
        window.close()


def test_preset_round_trip_restores_new_sampling_state(qt_app) -> None:
    recent_store = Path.cwd() / ".pytest-artifacts" / "recent_presets.json"
    preset_path = Path.cwd() / ".pytest-artifacts" / "workflow.chi-preset"
    recent_store.parent.mkdir(parents=True, exist_ok=True)
    window = MainWindow(preset_service=PresetFileService(recent_store_path=recent_store))
    try:
        row = window.phase_editors[0]
        row.label_edit.setText("实验工步")
        row.time_mode_combo.setCurrentIndex(row.time_mode_combo.findData("fixed"))
        row.fixed_mode_combo.setCurrentIndex(row.fixed_mode_combo.findData("point_count"))
        row.fixed_total_duration_edit.setText("240")
        row.fixed_point_count_edit.setText("8")
        window.save_preset_to_path(preset_path)
        row.label_edit.setText("已改动")
        row.fixed_point_count_edit.setText("3")
        window.load_preset_from_path(preset_path)
        qt_app.processEvents()
        restored = window.phase_editors[0].collect_state()
        assert restored.label == "实验工步"
        assert restored.sampling_mode.value == "fixed"
        assert restored.fixed_mode.value == "point_count"
        assert restored.fixed_point_count == "8"
        assert window.recent_presets_combo.count() >= 1
    finally:
        window.close()


def test_old_preset_modes_are_downgraded_on_load(qt_app) -> None:
    recent_store = Path.cwd() / ".pytest-artifacts" / "recent_presets_compat.json"
    preset_path = Path.cwd() / ".pytest-artifacts" / "compat.chi-preset"
    recent_store.parent.mkdir(parents=True, exist_ok=True)
    preset_path.write_text(
        """
        {
          "version": 2,
          "workspace_mode": "pulse_in_situ",
          "state": {
            "workspace_mode": "pulse_in_situ",
            "scheme_name": "compat",
            "file_prefix": "CHI",
            "export_dir": "",
            "active_material_mg": "1",
            "theoretical_capacity_mah_mg": "865",
            "phases": [
              {
                "label": "时间工步 1",
                "phase_kind": "time_points"
              }
            ],
            "impedance_mode": "galvanostatic",
            "geis_amplitude_a": "0.001",
            "estimated_resistance_ohm": "100"
          }
        }
        """,
        encoding="utf-8",
    )
    window = MainWindow(preset_service=PresetFileService(recent_store_path=recent_store))
    try:
        window.load_preset_from_path(preset_path)
        qt_app.processEvents()
        assert window.mode_combo.currentData() == WorkspaceMode.PULSE.value
    finally:
        window.close()


def test_loop_block_round_trip_is_preserved_in_preset(qt_app) -> None:
    recent_store = Path.cwd() / ".pytest-artifacts" / "recent_presets_loop.json"
    preset_path = Path.cwd() / ".pytest-artifacts" / "loop.chi-preset"
    recent_store.parent.mkdir(parents=True, exist_ok=True)
    window = MainWindow(preset_service=PresetFileService(recent_store_path=recent_store))
    try:
        window.add_voltage_phase_button.click()
        QTest.qWait(120)
        qt_app.processEvents()
        window.phase_editors[0].set_selected(True)
        window.phase_editors[1].set_selected(True)
        window.create_loop_button.click()
        QTest.qWait(120)
        qt_app.processEvents()
        window.save_preset_to_path(preset_path)
        window.new_preset()
        window.load_preset_from_path(preset_path)
        qt_app.processEvents()
        state = window._collect_state()
        assert len(state.workflow_items) == 1
        assert state.workflow_items[0].item_kind.value == "loop"
        assert state.workflow_items[0].repeat_count == 2
    finally:
        window.close()
