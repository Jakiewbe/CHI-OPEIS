from __future__ import annotations

from PySide6.QtWidgets import QScrollArea, QSplitter

from chi_generator.app import build_application
from chi_generator.domain.models import SamplingMode
from chi_generator.ui.models import PhaseUiKind
from chi_generator.ui.widgets import PresetComboBox


def _input_layout(window):
    scroll = window.findChild(QScrollArea, "leftScrollArea")
    assert scroll is not None
    body = scroll.widget()
    assert body is not None
    layout = body.layout()
    assert layout is not None
    return layout


def test_offscreen_main_window_keeps_right_panel_narrow(qt_app) -> None:
    app, window = build_application()
    try:
        window.resize(1600, 960)
        window.show()
        app.processEvents()
        splitter = window.findChild(QSplitter)
        assert splitter is not None
        left_width, right_width = splitter.sizes()
        assert left_width > right_width
        assert right_width > 0
        assert window.right_panel.maximumWidth() <= 560
    finally:
        window.close()


def test_workstep_editor_is_front_loaded_and_seeded(qt_app) -> None:
    app, window = build_application()
    try:
        layout = _input_layout(window)
        children = [layout.itemAt(index).widget() for index in range(layout.count()) if layout.itemAt(index).widget() is not None]
        assert children[:4] == [window.workspace_card, window.project_card, window.battery_card, window.workstep_card]
        assert len(window.phase_editors) == 1
        row = window.phase_editors[0]
        assert row.phase_kind_combo.currentData() == PhaseUiKind.TIME_POINTS.value
        assert row.time_mode_combo.currentData() == SamplingMode.SEGMENTED.value
        assert "24" in row.point_count_label.text()
        assert "EIS" in row.point_count_label.text()
    finally:
        window.close()


def test_preview_panel_keeps_summary_and_single_minimal_editor(qt_app) -> None:
    app, window = build_application()
    try:
        assert hasattr(window.output_panel, "summary_label")
        assert hasattr(window.output_panel, "minimal_editor")
        assert hasattr(window.output_panel, "copy_minimal_button")
        assert window.output_panel.summary_label.isReadOnly() is True
        assert window.output_panel.summary_label.minimumHeight() >= 120
        assert not hasattr(window.output_panel, "comment_editor")
    finally:
        window.close()


def test_project_and_sampling_controls_expose_browse_and_presets(qt_app) -> None:
    app, window = build_application()
    try:
        assert hasattr(window, "export_dir_browse_button")
        assert window.export_dir_browse_button.text()
        row = window.phase_editors[0]
        assert isinstance(row.sample_interval_edit, PresetComboBox)
        assert row.sample_interval_edit.currentText() == "1"
        assert isinstance(window.pulse_sample_interval_edit, PresetComboBox)
        assert window.pulse_sample_interval_edit.currentText() == "1"
        assert window.pulse_tail_enabled_box.isChecked() is False
        assert window.pulse_tail_rate_edit.isVisible() is False
    finally:
        window.close()
