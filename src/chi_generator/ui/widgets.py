"""Reusable Qt widgets for the GUI."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from chi_generator.domain.models import ProcessDirection, Severity, TimeBasisMode, ValidationIssue
from chi_generator.ui.models import CurrentInputUiMode, GuiPhaseState, PhaseUiKind


def fixed_font_family() -> str:
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


class Card(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(10)
        layout.addLayout(self.content_layout)


class NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # pragma: no cover
        event.ignore()


class PresetComboBox(NoWheelComboBox):
    def __init__(self, values: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for value in values:
            self.addItem(value, value)
        self.lineEdit().textChanged.connect(self._sync_edit_text)

    def _sync_edit_text(self, _text: str) -> None:
        # Hook point for shared textChanged listeners through the embedded line edit.
        return


class ScriptEditor(QPlainTextEdit):
    def wheelEvent(self, event) -> None:  # pragma: no cover
        super().wheelEvent(event)
        event.accept()


class SummaryPanel(QPlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(188)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self.setPlainText(text)


class IssueListWidget(QListWidget):
    def set_issues(self, issues: list[ValidationIssue]) -> None:
        self.clear()
        if not issues:
            self.addItem(QListWidgetItem("当前没有警告或错误。"))
            return
        for issue in issues:
            prefix = issue.severity.value.upper()
            item = QListWidgetItem(f"[{prefix}] {issue.field or '-'}: {issue.message}")
            if issue.severity is Severity.ERROR:
                item.setForeground(Qt.GlobalColor.red)
            elif issue.severity is Severity.WARNING:
                item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                item.setForeground(Qt.GlobalColor.darkCyan)
            self.addItem(item)


class ScriptOutputPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._copy_feedback_timer = QTimer(self)
        self._copy_feedback_timer.setSingleShot(True)
        self._copy_feedback_timer.setInterval(1200)
        self._copy_feedback_timer.timeout.connect(self._reset_copy_button)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.summary_label = SummaryPanel(self)
        self.summary_label.setPlainText("等待预览")
        self.summary_label.setObjectName("summaryPanel")
        root.addWidget(self.summary_label)

        self.editor_title = QLabel("极简版")
        self.editor_title.setObjectName("panelLabel")
        root.addWidget(self.editor_title)

        self.minimal_editor = ScriptEditor()
        self.minimal_editor.setReadOnly(True)
        self.minimal_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = self.minimal_editor.font()
        font.setFamily(fixed_font_family())
        self.minimal_editor.setFont(font)
        root.addWidget(self.minimal_editor)

        button_row = QHBoxLayout()
        self.copy_minimal_button = QPushButton("复制极简版")
        self.copy_minimal_button.setObjectName("secondaryButton")
        self.copy_minimal_button.clicked.connect(self._handle_copy_minimal)
        button_row.addWidget(self.copy_minimal_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

    def _set_editor_text(self, editor: QPlainTextEdit, text: str) -> None:
        if editor.toPlainText() == text:
            return
        vertical_value = editor.verticalScrollBar().value()
        horizontal_value = editor.horizontalScrollBar().value()
        editor.setPlainText(text)
        editor.verticalScrollBar().setValue(vertical_value)
        editor.horizontalScrollBar().setValue(horizontal_value)

    def _handle_copy_minimal(self) -> None:
        text = self.minimal_editor.toPlainText()
        if not text.strip():
            return
        QApplication.clipboard().setText(text)
        self.copy_minimal_button.setText("已复制")
        self.copy_minimal_button.setProperty("copied", True)
        self.copy_minimal_button.style().unpolish(self.copy_minimal_button)
        self.copy_minimal_button.style().polish(self.copy_minimal_button)
        self._copy_feedback_timer.start()

    def _reset_copy_button(self) -> None:
        self.copy_minimal_button.setText("复制极简版")
        self.copy_minimal_button.setProperty("copied", False)
        self.copy_minimal_button.style().unpolish(self.copy_minimal_button)
        self.copy_minimal_button.style().polish(self.copy_minimal_button)

    def set_scripts(self, commented: str, minimal: str, summary: str, can_copy: bool) -> None:
        del commented
        self._set_editor_text(self.minimal_editor, minimal)
        self.summary_label.setText(summary)
        self.copy_minimal_button.setEnabled(can_copy and bool(minimal.strip()))
        if not (can_copy and bool(minimal.strip())):
            self._reset_copy_button()


class WorkstepEditorRow(QFrame):
    def __init__(
        self,
        index: int,
        state: GuiPhaseState,
        *,
        on_change: Callable[[], None],
        on_move_up: Callable[["WorkstepEditorRow"], None],
        on_move_down: Callable[["WorkstepEditorRow"], None],
        on_delete: Callable[["WorkstepEditorRow"], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("workstepRow", True)
        self.index = index
        self.on_change = on_change
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.on_delete = on_delete
        self._build_ui()
        self.set_state(state)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        header_top = QHBoxLayout()
        header_top.setSpacing(8)
        self.order_badge = QLabel(f"S{self.index:02d}")
        self.order_badge.setObjectName("stepBadge")
        self.order_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.order_badge.setMinimumWidth(52)
        self.label_edit = self._line_edit("工步名称")
        self.label_edit.setMinimumWidth(180)
        self.phase_kind_combo = self._combo(
            [
                ("固定时间点", PhaseUiKind.TIME_POINTS.value),
                ("固定电压点", PhaseUiKind.VOLTAGE_POINTS.value),
                ("静置", PhaseUiKind.REST.value),
            ]
        )
        self.direction_combo = self._combo([("放电", ProcessDirection.DISCHARGE.value), ("充电", ProcessDirection.CHARGE.value)])
        self.current_mode_combo = self._combo([("倍率", CurrentInputUiMode.RATE.value), ("绝对电流", CurrentInputUiMode.ABSOLUTE.value)])
        self.rate_edit = self._line_edit("倍率/C")
        self.current_edit = self._line_edit("电流/A")
        for widget, width in (
            (self.phase_kind_combo, 132),
            (self.direction_combo, 96),
            (self.current_mode_combo, 108),
            (self.rate_edit, 128),
            (self.current_edit, 128),
        ):
            widget.setMinimumWidth(width)
        header_top.addWidget(self.order_badge)
        header_top.addWidget(self.label_edit, 1)
        header_top.addWidget(self.phase_kind_combo)
        header_top.addWidget(self.direction_combo)
        header_top.addWidget(self.current_mode_combo)
        header_top.addWidget(self.rate_edit)
        header_top.addWidget(self.current_edit)
        root.addLayout(header_top)

        header_bottom = QHBoxLayout()
        header_bottom.setSpacing(10)
        self.phase_hint_label = QLabel("每个工步独立控制方向、取点和 EIS。", self)
        self.phase_hint_label.setObjectName("phaseHint")
        self.insert_eis_box = QCheckBox("每点后测 EIS")
        self.insert_eis_box.toggled.connect(self._handle_change)
        self.point_count_label = QLabel("0 点 / 0 EIS")
        self.point_count_label.setObjectName("pointPill")
        self.move_up_button = QPushButton("上移")
        self.move_down_button = QPushButton("下移")
        self.delete_button = QPushButton("删除")
        for button in (self.move_up_button, self.move_down_button, self.delete_button):
            button.setObjectName("rowGhostButton")
            button.setMinimumWidth(60)
        self.move_up_button.clicked.connect(lambda: self.on_move_up(self))
        self.move_down_button.clicked.connect(lambda: self.on_move_down(self))
        self.delete_button.clicked.connect(lambda: self.on_delete(self))
        header_bottom.addWidget(self.phase_hint_label)
        header_bottom.addStretch(1)
        header_bottom.addWidget(self.insert_eis_box)
        header_bottom.addWidget(self.point_count_label)
        header_bottom.addWidget(self.move_up_button)
        header_bottom.addWidget(self.move_down_button)
        header_bottom.addWidget(self.delete_button)
        root.addLayout(header_bottom)

        self.detail_grid = QGridLayout()
        self.detail_grid.setContentsMargins(0, 4, 0, 0)
        self.detail_grid.setHorizontalSpacing(14)
        self.detail_grid.setVerticalSpacing(10)
        self.detail_grid.setColumnStretch(0, 1)
        self.detail_grid.setColumnStretch(1, 1)
        self.detail_grid.setColumnStretch(2, 1)
        root.addLayout(self.detail_grid)

        self.time_basis_combo = self._combo([("有效进度累计", TimeBasisMode.ACTIVE_PROGRESS.value), ("中断补偿", TimeBasisMode.INTERRUPTION_COMPENSATED.value)])
        self.manual_eis_edit = self._line_edit("单次 EIS 等效时长/s")
        self.early_duration_edit = self._line_edit("前期时长/min")
        self.early_count_edit = self._line_edit("前期点数")
        self.plateau_duration_edit = self._line_edit("平台时长/min")
        self.plateau_count_edit = self._line_edit("平台点数")
        self.late_duration_edit = self._line_edit("后期时长/min")
        self.late_count_edit = self._line_edit("后期点数")
        self.pre_wait_edit = self._line_edit("阶段前等待/s")
        self.sample_interval_edit = self._preset_combo(["0.001", "0.002", "0.005", "0.01", "0.1", "1"])
        self.voltage_start_edit = self._line_edit("起点/V")
        self.voltage_end_edit = self._line_edit("终点/V")
        self.voltage_step_edit = self._line_edit("步长/V")
        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("高级设置")
        self.advanced_toggle.setObjectName("inlineButton")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.toggled.connect(self._sync_visibility)
        self.upper_voltage_edit = self._line_edit("电压上限/V")
        self.lower_voltage_edit = self._line_edit("电压下限/V")
        self.rest_duration_edit = self._line_edit("静置时长/s")

        self.time_basis_block = self._field_block("时间基准", self.time_basis_combo)
        self.manual_eis_block = self._field_block("补偿时长/s", self.manual_eis_edit)
        self.early_duration_block = self._field_block("前期时长/min", self.early_duration_edit)
        self.early_count_block = self._field_block("前期点数", self.early_count_edit)
        self.plateau_duration_block = self._field_block("平台时长/min", self.plateau_duration_edit)
        self.plateau_count_block = self._field_block("平台点数", self.plateau_count_edit)
        self.late_duration_block = self._field_block("后期时长/min", self.late_duration_edit)
        self.late_count_block = self._field_block("后期点数", self.late_count_edit)
        self.pre_wait_block = self._field_block("阶段前等待/s", self.pre_wait_edit)
        self.sample_interval_block = self._field_block("采样间隔/s", self.sample_interval_edit)
        self.voltage_start_block = self._field_block("起点/V", self.voltage_start_edit)
        self.voltage_end_block = self._field_block("终点/V", self.voltage_end_edit)
        self.voltage_step_block = self._field_block("步长/V", self.voltage_step_edit)
        self.advanced_block = self._field_block("高级设置", self.advanced_toggle)
        self.upper_voltage_block = self._field_block("电压上限/V", self.upper_voltage_edit)
        self.lower_voltage_block = self._field_block("电压下限/V", self.lower_voltage_edit)
        self.rest_duration_block = self._field_block("静置时长/s", self.rest_duration_edit)
        self._all_detail_blocks = [
            self.time_basis_block,
            self.manual_eis_block,
            self.early_duration_block,
            self.early_count_block,
            self.plateau_duration_block,
            self.plateau_count_block,
            self.late_duration_block,
            self.late_count_block,
            self.pre_wait_block,
            self.sample_interval_block,
            self.voltage_start_block,
            self.voltage_end_block,
            self.voltage_step_block,
            self.advanced_block,
            self.upper_voltage_block,
            self.lower_voltage_block,
            self.rest_duration_block,
        ]

    def _line_edit(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit(self)
        edit.setPlaceholderText(placeholder)
        edit.textChanged.connect(self._handle_change)
        return edit

    def _combo(self, items: list[tuple[str, str]]) -> NoWheelComboBox:
        combo = NoWheelComboBox(self)
        for label, value in items:
            combo.addItem(label, value)
        combo.currentIndexChanged.connect(self._sync_visibility)
        combo.currentIndexChanged.connect(self._handle_change)
        return combo

    def _preset_combo(self, values: list[str]) -> PresetComboBox:
        combo = PresetComboBox(values, self)
        combo.currentIndexChanged.connect(self._handle_change)
        combo.lineEdit().textChanged.connect(self._handle_change)
        return combo

    def _field_block(self, title: str, field: QWidget) -> QWidget:
        block = QWidget(self)
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(title, block)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(field)
        return block

    def _clear_grid(self) -> None:
        while self.detail_grid.count():
            item = self.detail_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                self.detail_grid.removeWidget(widget)

    def _add_grid_row(self, row: int, *widgets: QWidget) -> None:
        for column, widget in enumerate(widgets):
            widget.show()
            self.detail_grid.addWidget(widget, row, column)

    def _refresh_grid(self) -> None:
        self._clear_grid()
        for block in self._all_detail_blocks:
            block.hide()
        phase_kind = PhaseUiKind(self.phase_kind_combo.currentData())
        current_mode = CurrentInputUiMode(self.current_mode_combo.currentData())
        self.rate_edit.setVisible(current_mode is CurrentInputUiMode.RATE and phase_kind is not PhaseUiKind.REST)
        self.current_edit.setVisible(current_mode is CurrentInputUiMode.ABSOLUTE and phase_kind is not PhaseUiKind.REST)

        if phase_kind is PhaseUiKind.TIME_POINTS:
            self.phase_hint_label.setText("时间工步按前期、平台和后期三段独立分配取点。")
            self._add_grid_row(0, self.time_basis_block, self.early_duration_block, self.early_count_block)
            self._add_grid_row(1, self.plateau_duration_block, self.plateau_count_block, self.late_duration_block)
            self._add_grid_row(2, self.late_count_block, self.pre_wait_block, self.sample_interval_block)
            self._add_grid_row(3, self.advanced_block)
            row_index = 4
            if self.advanced_toggle.isChecked():
                self._add_grid_row(row_index, self.upper_voltage_block, self.lower_voltage_block)
                row_index += 1
            if self.time_basis_combo.currentData() == TimeBasisMode.INTERRUPTION_COMPENSATED.value:
                self._add_grid_row(row_index, self.manual_eis_block)
        elif phase_kind is PhaseUiKind.VOLTAGE_POINTS:
            self.phase_hint_label.setText("电压工步按起点、终点和步长自动展开取点。")
            self._add_grid_row(0, self.voltage_start_block, self.voltage_end_block, self.voltage_step_block)
            self._add_grid_row(1, self.pre_wait_block, self.sample_interval_block, self.advanced_block)
            if self.advanced_toggle.isChecked():
                self._add_grid_row(2, self.upper_voltage_block, self.lower_voltage_block)
        else:
            self.phase_hint_label.setText("静置工步只保留持续时间，不参与取点。")
            self._add_grid_row(0, self.rest_duration_block)

    def _safe_int(self, text: str) -> int:
        try:
            return int(text or "0")
        except ValueError:
            return 0

    def _voltage_point_count(self) -> int:
        try:
            start = float(self.voltage_start_edit.text() or "0")
            end = float(self.voltage_end_edit.text() or "0")
            step = float(self.voltage_step_edit.text() or "0")
        except ValueError:
            return 0
        if start == end or step <= 0:
            return 0
        quotient = abs(start - end) / step
        rounded = round(quotient)
        if abs(quotient - rounded) > 1e-6:
            return 0
        return int(rounded) + 1

    def _refresh_point_badge(self) -> None:
        phase_kind = PhaseUiKind(self.phase_kind_combo.currentData())
        if phase_kind is PhaseUiKind.TIME_POINTS:
            point_count = sum(self._safe_int(edit.text()) for edit in (self.early_count_edit, self.plateau_count_edit, self.late_count_edit))
        elif phase_kind is PhaseUiKind.VOLTAGE_POINTS:
            point_count = self._voltage_point_count()
        else:
            point_count = 0
        eis_count = point_count if self.insert_eis_box.isChecked() and phase_kind is not PhaseUiKind.REST else 0
        self.point_count_label.setText(f"{point_count} 点 / {eis_count} EIS")

    def _sync_visibility(self) -> None:
        phase_kind = PhaseUiKind(self.phase_kind_combo.currentData())
        self.direction_combo.setVisible(phase_kind is not PhaseUiKind.REST)
        self.current_mode_combo.setVisible(phase_kind is not PhaseUiKind.REST)
        self.insert_eis_box.setVisible(phase_kind is not PhaseUiKind.REST)
        self._refresh_grid()
        self._refresh_point_badge()

    def _handle_change(self) -> None:
        self._refresh_point_badge()
        self.on_change()

    def set_order_state(self, index: int, total: int) -> None:
        self.index = index
        self.order_badge.setText(f"S{index:02d}")
        self.move_up_button.setEnabled(index > 1)
        self.move_down_button.setEnabled(index < total)
        self.delete_button.setEnabled(total > 1)

    def set_state(self, state: GuiPhaseState) -> None:
        def set_combo(combo: QComboBox, value: str) -> None:
            combo.setCurrentIndex(combo.findData(value))

        self.label_edit.setText(state.label)
        set_combo(self.phase_kind_combo, state.phase_kind.value)
        set_combo(self.direction_combo, state.direction.value)
        set_combo(self.current_mode_combo, state.current_mode.value)
        self.rate_edit.setText(state.rate_c)
        self.current_edit.setText(state.current_a)
        self.insert_eis_box.setChecked(state.insert_eis_after_each_point)
        self.pre_wait_edit.setText(state.pre_wait_s)
        self.sample_interval_edit.setEditText(state.sample_interval_s)
        self.voltage_start_edit.setText(state.voltage_start_v)
        self.voltage_end_edit.setText(state.voltage_end_v)
        self.voltage_step_edit.setText(state.voltage_step_v)
        self.upper_voltage_edit.setText(state.upper_voltage_v)
        self.lower_voltage_edit.setText(state.lower_voltage_v)
        set_combo(self.time_basis_combo, state.time_basis_mode.value)
        self.manual_eis_edit.setText(state.manual_eis_duration_s)
        self.early_duration_edit.setText(state.early_duration_min)
        self.early_count_edit.setText(state.early_point_count)
        self.plateau_duration_edit.setText(state.plateau_duration_min)
        self.plateau_count_edit.setText(state.plateau_point_count)
        self.late_duration_edit.setText(state.late_duration_min)
        self.late_count_edit.setText(state.late_point_count)
        self.rest_duration_edit.setText(state.rest_duration_s)
        self._sync_visibility()

    def collect_state(self) -> GuiPhaseState:
        return GuiPhaseState.model_validate(
            {
                "label": self.label_edit.text() or f"工步 {self.index}",
                "phase_kind": self.phase_kind_combo.currentData(),
                "direction": self.direction_combo.currentData(),
                "current_mode": self.current_mode_combo.currentData(),
                "rate_c": self.rate_edit.text(),
                "current_a": self.current_edit.text(),
                "pre_wait_s": self.pre_wait_edit.text(),
                "sample_interval_s": self.sample_interval_edit.currentText(),
                "insert_eis_after_each_point": self.insert_eis_box.isChecked(),
                "voltage_start_v": self.voltage_start_edit.text(),
                "voltage_end_v": self.voltage_end_edit.text(),
                "voltage_step_v": self.voltage_step_edit.text(),
                "upper_voltage_v": self.upper_voltage_edit.text(),
                "lower_voltage_v": self.lower_voltage_edit.text(),
                "time_basis_mode": self.time_basis_combo.currentData(),
                "manual_eis_duration_s": self.manual_eis_edit.text(),
                "early_duration_min": self.early_duration_edit.text(),
                "early_point_count": self.early_count_edit.text(),
                "plateau_duration_min": self.plateau_duration_edit.text(),
                "plateau_point_count": self.plateau_count_edit.text(),
                "late_duration_min": self.late_duration_edit.text(),
                "late_point_count": self.late_count_edit.text(),
                "rest_duration_s": self.rest_duration_edit.text(),
            }
        )


PhaseEditor = WorkstepEditorRow
WorkstepRow = WorkstepEditorRow


__all__ = [
    "Card",
    "IssueListWidget",
    "NoWheelComboBox",
    "PresetComboBox",
    "PhaseEditor",
    "ScriptEditor",
    "ScriptOutputPanel",
    "WorkstepRow",
    "WorkstepEditorRow",
    "fixed_font_family",
]
