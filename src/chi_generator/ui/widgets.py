"""Reusable Qt widgets for the Fluent GUI."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QListWidgetItem, QPlainTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import CheckBox, ComboBox, EditableComboBox, LineEdit, ListWidget, PlainTextEdit, PrimaryPushButton, PushButton, SimpleCardWidget, StrongBodyLabel

from chi_generator.domain.calculations import calculate_ctc_recommendation, expand_voltage_range
from chi_generator.domain.models import ProcessDirection, RiskLevel, SamplingMode, Severity, ValidationIssue
from chi_generator.ui.models import CurrentInputUiMode, FixedTimeUiMode, GuiLoopState, GuiPhaseState, GuiTimeSegmentState, PhaseUiKind, VoltageInputUiMode
from chi_generator.ui.planning import parse_float_list


def fixed_font_family() -> str:
    return QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


class Card(SimpleCardWidget):
    def __init__(self, title: str, parent: QWidget | None = None, subtitle: str = "") -> None:
        super().__init__(parent)
        self.setProperty("isCard", True)
        self.setObjectName("cardWidget")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)
        title_label = StrongBodyLabel(title, self)
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle, self)
            subtitle_label.setObjectName("cardSubtitle")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(12)
        layout.addLayout(self.content_layout)


class NoWheelComboBox(ComboBox):
    def addItem(self, text, userData=None) -> None:
        super().addItem(text, userData=userData)

    def wheelEvent(self, event) -> None:  # pragma: no cover
        event.ignore()


class PresetComboBox(EditableComboBox):
    def __init__(self, values: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        for value in values:
            self.addItem(value, value)
        self.textChanged.connect(self._sync_edit_text)

    def addItem(self, text, userData=None) -> None:
        super().addItem(text, userData=userData)

    def lineEdit(self) -> "PresetComboBox":
        return self

    def setEditText(self, text: str) -> None:
        self.setText(text)

    def _sync_edit_text(self, _text: str) -> None:
        return


class ScriptEditor(PlainTextEdit):
    def wheelEvent(self, event) -> None:  # pragma: no cover
        super().wheelEvent(event)
        event.accept()


class SummaryPanel(PlainTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(PlainTextEdit.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(120)
        self.setMaximumHeight(140)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:
        self.setPlainText(text)


class IssueListWidget(ListWidget):
    _code_map = {
        "dense_eis_low_frequency": "低频端设置为 0.01 Hz，判定为高风险密集取点。",
        "long_single_eis_duration": "当前单次 EIS 持续时间较长。",
        "interrupted_progress": "EIS 插入过于频繁，会明显打断恒流轨迹。",
        "high_compensation_total": "中断补偿累计时间较大，会拉长后续恒流历时。",
        "frequent_direction_switches": "工步切换充放电方向较频繁，请确认流程设计。",
        "rest_dominates_sequence": "静置总时长超过电化学工作时长，请确认是否符合预期。",
        "soc_depletion_risk": "SoC 仿真显示在全部 EIS 完成前可能已经耗尽。",
        "ctc_enabled": "已启用等效容量补偿。",
        "missing_phases": "至少需要一个工步。",
        "phase_invalid": "工步参数无效。",
        "missing_pulse": "脉冲模式缺少脉冲参数。",
        "ui.refresh": "界面预览刷新失败。",
    }

    _hint_map = {
        "dense_eis_low_frequency": "风险预估按长时低频 EIS 处理。",
        "long_single_eis_duration": "当前估算的单次扫描时间较长。",
        "interrupted_progress": "建议降低取点密度，或只在关键点插入 EIS。",
        "high_compensation_total": "建议检查中断补偿模式是否过密。",
        "soc_depletion_risk": "采样看板中的红点表示预测会丢失的点位。",
        "ctc_enabled": "适用于需要锁定总等效放电量的测试。",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)

    def _format_issue(self, issue: ValidationIssue) -> str:
        severity_map = {Severity.ERROR: "错误", Severity.WARNING: "警告", Severity.INFO: "提示"}
        field_map = {"impedance_defaults.low_frequency_hz": "阻抗低频", "phases": "工步", "pulse": "脉冲参数"}
        message = self._code_map.get(issue.code, issue.message)
        if issue.code == "phase_invalid" and issue.message:
            message = issue.message
        hint = self._hint_map.get(issue.code, issue.hint)
        field = field_map.get(issue.field or "", issue.field or "-")
        text = f"[{severity_map[issue.severity]}] {field}: {message}"
        if hint:
            text += f"\n提示：{hint}"
        return text

    def set_issues(self, issues: list[ValidationIssue]) -> None:
        self.clear()
        if not issues:
            self.addItem(QListWidgetItem("当前没有警告或错误。"))
            return
        for issue in issues:
            item = QListWidgetItem(self._format_issue(issue))
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
        root.setSpacing(10)
        self.summary_label = SummaryPanel(self)
        self.summary_label.setPlainText("等待预览生成")
        self.summary_label.setObjectName("summaryPanel")
        root.addWidget(self.summary_label, 0)
        self.editor_title = QLabel("最简脚本", self)
        self.editor_title.setObjectName("panelLabel")
        root.addWidget(self.editor_title)
        self.minimal_editor = ScriptEditor()
        self.minimal_editor.setReadOnly(True)
        self.minimal_editor.setLineWrapMode(PlainTextEdit.LineWrapMode.NoWrap)
        font = self.minimal_editor.font()
        font.setFamily(fixed_font_family())
        self.minimal_editor.setFont(font)
        self.minimal_editor.setMinimumHeight(260)
        root.addWidget(self.minimal_editor, 1)
        button_row = QHBoxLayout()
        self.copy_minimal_button = PrimaryPushButton(self)
        self.copy_minimal_button.setText("复制最简脚本")
        self.copy_minimal_button.clicked.connect(self._handle_copy_minimal)
        button_row.addWidget(self.copy_minimal_button)
        button_row.addStretch(1)
        root.addLayout(button_row)

    def _set_editor_text(self, editor: PlainTextEdit, text: str) -> None:
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
        self._copy_feedback_timer.start()

    def _reset_copy_button(self) -> None:
        self.copy_minimal_button.setText("复制最简脚本")

    def set_scripts(self, commented: str, minimal: str, summary: str, can_copy: bool) -> None:
        del commented
        self._set_editor_text(self.minimal_editor, minimal)
        self.summary_label.setText(summary)
        self.copy_minimal_button.setEnabled(can_copy and bool(minimal.strip()))
        if not (can_copy and bool(minimal.strip())):
            self._reset_copy_button()


class ManualPointDialog(QDialog):
    def __init__(self, *, title: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(460, 320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        hint = QLabel("支持粘贴逗号、空格或换行分隔的数值。时间列表输入累计分钟，电压列表输入伏特。", self)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.editor = PlainTextEdit(self)
        self.editor.setPlainText(text)
        font = self.editor.font()
        font.setFamily(fixed_font_family())
        self.editor.setFont(font)
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> str:
        return self.editor.toPlainText().strip()


class GuidedManualPointDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        text: str,
        is_voltage: bool = False,
        direction: ProcessDirection | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(460, 320)
        self.setStyleSheet(
            "QDialog {"
            " background-color: #f3f5f7;"
            "}"
            "QLabel {"
            " color: #5f6b7a;"
            "}"
            "QDialogButtonBox QPushButton {"
            " min-width: 72px;"
            " color: #1d2329;"
            "}"
            "QDialogButtonBox QPushButton:disabled {"
            " color: #1d2329;"
            "}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint_parts = ["支持粘贴逗号、空格或换行分隔的数值。时间列表输入累计分钟，电压列表输入伏特。"]
        if is_voltage and direction is ProcessDirection.DISCHARGE:
            hint_parts.append("当前工步为放电，建议按从高到低输入，例如 3.20 3.05 2.92 2.80。")
        elif is_voltage and direction is ProcessDirection.CHARGE:
            hint_parts.append("当前工步为充电，建议按从低到高输入，例如 2.80 2.92 3.05 3.20。")
        hint = QLabel("\n".join(hint_parts), self)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.editor = QPlainTextEdit(self)
        self.editor.setPlainText(text)
        self.editor.setPlaceholderText("3.20\n3.05\n2.92\n2.80" if is_voltage else "10\n25\n40\n60")
        self.editor.setStyleSheet(
            "QPlainTextEdit {"
            " background-color: #f7f8fa;"
            " color: #1d2329;"
            " border: 1px solid #b8c0cc;"
            " border-radius: 8px;"
            " padding: 8px;"
            " selection-background-color: #cfd6df;"
            " selection-color: #1d2329;"
            "}"
            "QPlainTextEdit:focus {"
            " border: 1px solid #98a2b3;"
            "}"
        )
        font = self.editor.font()
        font.setFamily(fixed_font_family())
        self.editor.setFont(font)
        layout.addWidget(self.editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> str:
        return self.editor.toPlainText().strip()







def _set_combo_texts_clean(combo, texts: list[str]) -> None:
    for index, text in enumerate(texts):
        if index < combo.count():
            combo.setItemText(index, text)


def _script_output_init_clean(self: ScriptOutputPanel, parent: QWidget | None = None) -> None:
    _ORIGINAL_SCRIPT_OUTPUT_INIT(self, parent)
    self.summary_label.setPlainText("等待预览生成")
    self.editor_title.setText("极简脚本")
    self.copy_minimal_button.setText("复制极简脚本")


def _script_output_reset_copy_button_clean(self: ScriptOutputPanel) -> None:
    self.copy_minimal_button.setText("复制极简脚本")


def _workstep_sync_copy_clean(self: WorkstepEditorRow) -> None:
    self.label_edit.setPlaceholderText("可选名称（仅用于界面摘要）")
    _set_combo_texts_clean(self.phase_kind_combo, ["时间取点", "电压取点", "静置"])
    _set_combo_texts_clean(self.direction_combo, ["放电", "充电"])
    _set_combo_texts_clean(self.current_mode_combo, ["倍率", "绝对电流"])
    _set_combo_texts_clean(self.time_mode_combo, ["固定", "分段", "手动"])
    self.rate_edit.setPlaceholderText("倍率 / C")
    self.current_edit.setPlaceholderText("电流 / A")
    self.pre_wait_edit.setPlaceholderText("点前等待 / s")
    self.insert_eis_box.setText("每个点后插入 EIS")
    self.move_up_button.setText("上移")
    self.move_down_button.setText("下移")
    self.delete_button.setText("删除")
    self.smart_recommend_button.setText("推荐取点")
    self.manual_time_button.setText("编辑时间列表")
    self.manual_voltage_button.setText("编辑电压列表")
    self.add_segment_button.setText("新增分段")
    self.manual_time_status.setText(f"{self._count_values(self._manual_time_points_text)} 个值")
    self.manual_voltage_status.setText(f"{self._count_values(self._manual_voltage_points_text)} 个值")
    if "EIS" in self.point_count_label.text():
        self.point_count_label.setText(
            self.point_count_label.text().replace("鐐?/ ", "点 / ").replace("鐐?/", "点 / ").replace("娆?EIS", "次 EIS").replace("次EIS", "次 EIS")
        )
    phase_kind = self.phase_kind_combo.currentData()
    if phase_kind == PhaseUiKind.TIME_POINTS.value:
        self.phase_hint_label.setText("通过固定、分段或手动采样匹配放电过程的物理分区。")
    elif phase_kind == PhaseUiKind.VOLTAGE_POINTS.value:
        self.phase_hint_label.setText("电压工步可使用范围生成或手动列表，应对不可整除和非均匀取点。")
    else:
        self.phase_hint_label.setText("静置工步表示真正独立的静置阶段。")
    for segment in getattr(self, "segment_editors", []):
        segment.label.setText(f"分段 {segment.index + 1}")
        segment.remove_button.setText("删除")


def _workstep_set_state_clean(self: WorkstepEditorRow, state: GuiPhaseState) -> None:
    _ORIGINAL_WORKSTEP_SET_STATE(self, state)
    _workstep_sync_copy_clean(self)


def _workstep_sync_visibility_clean(self: WorkstepEditorRow) -> None:
    _ORIGINAL_WORKSTEP_SYNC_VISIBILITY(self)
    _workstep_sync_copy_clean(self)


def _workstep_set_order_state_clean(self: WorkstepEditorRow, index: int, total: int) -> None:
    _ORIGINAL_WORKSTEP_SET_ORDER_STATE(self, index, total)
    _workstep_sync_copy_clean(self)


def _loop_sync_copy_clean(self: LoopBlockWidget) -> None:
    self.duplicate_button.setText("复制块")
    self.move_up_button.setText("上移")
    self.move_down_button.setText("下移")
    self.delete_button.setText("删除")
    self.expand_button.setText("折叠" if self.body.isVisible() else "展开")
    self.summary_label.setText(
        f"包含 {len(self.phase_rows)} 个工步，每轮展开 {len(self.phase_rows)} 个，当前重复次数 {self.repeat_count_edit.text() or '2'}。"
    )


def _loop_set_state_clean(self: LoopBlockWidget, state: GuiLoopState) -> None:
    _ORIGINAL_LOOP_SET_STATE(self, state)
    _loop_sync_copy_clean(self)


def _loop_set_order_state_clean(self: LoopBlockWidget, index: int, total: int) -> None:
    _ORIGINAL_LOOP_SET_ORDER_STATE(self, index, total)
    _loop_sync_copy_clean(self)


def _loop_toggle_body_clean(self: LoopBlockWidget) -> None:
    _ORIGINAL_LOOP_TOGGLE_BODY(self)
    _loop_sync_copy_clean(self)


def _issue_format_clean(self: IssueListWidget, issue: ValidationIssue) -> str:
    severity_map = {Severity.ERROR: "错误", Severity.WARNING: "警告", Severity.INFO: "提示"}
    field_map = {
        "impedance_defaults.low_frequency_hz": "阻抗低频",
        "phases": "工步",
        "pulse": "脉冲参数",
    }
    risk_map = {
        RiskLevel.BLOCKING: "阻断",
        RiskLevel.HIGH: "强警告",
        RiskLevel.MEDIUM: "警告",
        RiskLevel.LOW: "提示",
        None: "",
    }
    message = self._code_map.get(issue.code, issue.message)
    if issue.code == "phase_invalid" and issue.message:
        message = issue.message
    hint = self._hint_map.get(issue.code, issue.hint)
    field = field_map.get(issue.field or "", issue.field or "-")
    text = f"[{severity_map[issue.severity]}] {field}: {message}"
    risk_prefix = risk_map.get(issue.risk_level, "")
    if risk_prefix:
        text = f"[{risk_prefix}] {text}"
    if hint:
        text += f"\n提示：{hint}"
    return text


_ORIGINAL_SCRIPT_OUTPUT_INIT = ScriptOutputPanel.__init__
ScriptOutputPanel.__init__ = _script_output_init_clean
ScriptOutputPanel._reset_copy_button = _script_output_reset_copy_button_clean


class LoopCountDialog(QDialog):
    def __init__(self, *, title: str, repeat_count: int = 2, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(320, 120)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(QLabel("输入循环重复次数（至少 2）。", self))
        self.count_edit = LineEdit(self)
        self.count_edit.setPlaceholderText("重复次数")
        self.count_edit.setText(str(repeat_count))
        layout.addWidget(self.count_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def repeat_count(self) -> int:
        return int(self.count_edit.text() or "2")


class SegmentEditor(QWidget):
    def __init__(self, index: int, state: GuiTimeSegmentState, on_change: Callable[[], None], on_remove: Callable[[int], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self._on_change = on_change
        self._on_remove = on_remove
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.label = QLabel(f"分段 {index + 1}", self)
        self.duration_edit = LineEdit(self)
        self.duration_edit.setPlaceholderText("时长")
        self.duration_edit.setMaximumWidth(92)
        self.duration_edit.setText(state.duration_min)
        self.point_count_edit = LineEdit(self)
        self.point_count_edit.setPlaceholderText("点数")
        self.point_count_edit.setMaximumWidth(92)
        self.point_count_edit.setText(state.point_count)
        self.remove_button = PushButton(self)
        self.remove_button.setText("删除")
        layout.addWidget(self.label)
        layout.addWidget(self.duration_edit)
        layout.addWidget(QLabel("min", self))
        layout.addWidget(self.point_count_edit)
        layout.addWidget(QLabel("点", self))
        layout.addStretch(1)
        layout.addWidget(self.remove_button)
        self.duration_edit.textChanged.connect(self._on_change)
        self.point_count_edit.textChanged.connect(self._on_change)
        self.remove_button.clicked.connect(lambda: self._on_remove(self.index))

    def set_index(self, index: int) -> None:
        self.index = index
        self.label.setText(f"分段 {index + 1}")

    def collect_state(self) -> GuiTimeSegmentState:
        return GuiTimeSegmentState(duration_min=self.duration_edit.text() or "0", point_count=self.point_count_edit.text() or "0")



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
        self._manual_time_points_text = ""
        self._manual_voltage_points_text = ""
        self.segment_editors: list[SegmentEditor] = []
        self._build_ui()
        self.set_state(state)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(12)

        header_top = QHBoxLayout()
        self.select_box = CheckBox(self)
        self.order_badge = QLabel(f"S{self.index:02d}")
        self.order_badge.setObjectName("stepBadge")
        self.order_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.order_badge.setMinimumWidth(52)
        self.label_edit = self._line_edit("工步标签（可留空自动命名）")
        self.label_edit.setToolTip("仅用于预览摘要和导出说明，不影响 CHI 命令。")
        self.phase_kind_combo = self._combo([("时间取点", PhaseUiKind.TIME_POINTS.value), ("电压取点", PhaseUiKind.VOLTAGE_POINTS.value), ("静置", PhaseUiKind.REST.value)])
        self.direction_combo = self._combo([("放电", ProcessDirection.DISCHARGE.value), ("充电", ProcessDirection.CHARGE.value)])
        self.current_mode_combo = self._combo([("倍率", CurrentInputUiMode.RATE.value), ("绝对电流", CurrentInputUiMode.ABSOLUTE.value)])
        self.rate_edit = self._line_edit("倍率 / C")
        self.current_edit = self._line_edit("电流 / A")
        header_top.addWidget(self.select_box)
        header_top.addWidget(self.order_badge)
        header_top.addWidget(self.label_edit, 1)
        header_top.addWidget(self.phase_kind_combo)
        header_top.addWidget(self.direction_combo)
        header_top.addWidget(self.current_mode_combo)
        header_top.addWidget(self.rate_edit)
        header_top.addWidget(self.current_edit)
        root.addLayout(header_top)

        header_bottom = QHBoxLayout()
        self.phase_hint_label = QLabel("在当前工步内配置采样点和 EIS 插入策略。", self)
        self.phase_hint_label.setObjectName("phaseHint")
        self.insert_eis_box = CheckBox("每个点后插入 EIS")
        self.insert_eis_box.toggled.connect(self._handle_change)
        self.point_count_label = QLabel("0 点 / 0 次 EIS")
        self.move_up_button = PushButton(self)
        self.move_up_button.setText("上移")
        self.move_down_button = PushButton(self)
        self.move_down_button.setText("下移")
        self.delete_button = PushButton(self)
        self.delete_button.setText("删除")
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

        self.pre_wait_edit = self._line_edit("点前等待 / s")
        self.sample_interval_edit = self._preset_combo(["1", "0.1", "0.01", "0.005", "0.002", "0.001"])
        self.upper_voltage_edit = self._line_edit("上限 / V")
        self.lower_voltage_edit = self._line_edit("下限 / V")
        self.common_row = self._row(
            self._field("点前等待 / s", self.pre_wait_edit),
            self._field("采样间隔 / s", self.sample_interval_edit),
            self._field("上限 / V", self.upper_voltage_edit),
            self._field("下限 / V", self.lower_voltage_edit),
        )
        root.addWidget(self.common_row)

        self.time_mode_combo = self._combo([("固定", SamplingMode.FIXED.value), ("分段", SamplingMode.SEGMENTED.value), ("手动", SamplingMode.MANUAL.value)])
        self.time_basis_combo = self._combo([("按有效进度", "active_progress"), ("按中断补偿", "interruption_compensated"), ("按等效容量补偿", "capacity_compensated")])
        self.manual_eis_edit = self._line_edit("EIS 时长覆盖 / s")
        self.smart_recommend_button = PushButton(self)
        self.smart_recommend_button.setText("推荐取点")
        self.smart_recommend_button.setToolTip("根据总时长和单次 EIS 时长，给出更保守的固定取点建议。")
        self.smart_recommend_button.clicked.connect(self._handle_smart_recommend)
        self.time_header_row = self._row(
            self._field("采样模式", self.time_mode_combo),
            self._field("时间基准", self.time_basis_combo),
            self._field("EIS 时长覆盖 / s", self.manual_eis_edit),
            self._field("取点建议", self.smart_recommend_button),
        )
        root.addWidget(self.time_header_row)

        self.fixed_mode_combo = self._combo([("按间隔", FixedTimeUiMode.INTERVAL.value), ("按点数", FixedTimeUiMode.POINT_COUNT.value)])
        self.fixed_total_duration_edit = self._line_edit("总时长 / min")
        self.fixed_interval_edit = self._line_edit("间隔 / min")
        self.fixed_point_count_edit = self._line_edit("总点数")
        self.fixed_row = self._row(
            self._field("固定方式", self.fixed_mode_combo),
            self._field("总时长 / min", self.fixed_total_duration_edit),
            self._field("间隔 / min", self.fixed_interval_edit),
            self._field("总点数", self.fixed_point_count_edit),
        )
        root.addWidget(self.fixed_row)

        self.manual_time_wrap = QWidget(self)
        manual_time_layout = QHBoxLayout(self.manual_time_wrap)
        manual_time_layout.setContentsMargins(0, 0, 0, 0)
        self.manual_time_button = PushButton(self)
        self.manual_time_button.setText("编辑时间列表")
        self.manual_time_status = QLabel("0 个值", self)
        manual_time_layout.addWidget(self.manual_time_button)
        manual_time_layout.addWidget(self.manual_time_status, 1)
        self.manual_time_button.clicked.connect(self._edit_manual_time_points)
        root.addWidget(self.manual_time_wrap)

        self.segment_panel = QWidget(self)
        segment_panel_layout = QVBoxLayout(self.segment_panel)
        segment_panel_layout.setContentsMargins(0, 0, 0, 0)
        toolbar = QHBoxLayout()
        self.add_segment_button = PushButton(self)
        self.add_segment_button.setText("新增分段")
        self.add_segment_button.clicked.connect(self._append_segment)
        toolbar.addWidget(self.add_segment_button)
        toolbar.addStretch(1)
        segment_panel_layout.addLayout(toolbar)
        self.segment_host = QVBoxLayout()
        self.segment_host.setSpacing(6)
        segment_panel_layout.addLayout(self.segment_host)
        root.addWidget(self.segment_panel)

        self.voltage_input_mode_combo = self._combo([("范围生成", VoltageInputUiMode.RANGE.value), ("手动列表", VoltageInputUiMode.MANUAL.value)])
        self.voltage_start_edit = self._line_edit("起始 / V")
        self.voltage_end_edit = self._line_edit("结束 / V")
        self.voltage_step_edit = self._line_edit("步长 / V")
        self.voltage_row = self._row(
            self._field("电压输入", self.voltage_input_mode_combo),
            self._field("起始 / V", self.voltage_start_edit),
            self._field("结束 / V", self.voltage_end_edit),
            self._field("步长 / V", self.voltage_step_edit),
        )
        root.addWidget(self.voltage_row)

        self.manual_voltage_wrap = QWidget(self)
        manual_voltage_layout = QHBoxLayout(self.manual_voltage_wrap)
        manual_voltage_layout.setContentsMargins(0, 0, 0, 0)
        self.manual_voltage_button = PushButton(self)
        self.manual_voltage_button.setText("编辑电压列表")
        self.manual_voltage_status = QLabel("0 个值", self)
        manual_voltage_layout.addWidget(self.manual_voltage_button)
        manual_voltage_layout.addWidget(self.manual_voltage_status, 1)
        self.manual_voltage_button.clicked.connect(self._edit_manual_voltage_points)
        root.addWidget(self.manual_voltage_wrap)

        self.rest_duration_edit = self._line_edit("静置时长 / s")
        self.rest_row = self._row(self._field("静置时长 / s", self.rest_duration_edit))
        root.addWidget(self.rest_row)

    def _line_edit(self, placeholder: str) -> LineEdit:
        edit = LineEdit(self)
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
        combo.textChanged.connect(self._handle_change)
        return combo

    def _field(self, title: str, field: QWidget) -> QWidget:
        block = QWidget(self)
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title, block)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(field)
        return block

    def _row(self, *widgets: QWidget) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            layout.addWidget(widget)
        layout.addStretch(1)
        return row

    def _rebuild_segments(self, states: list[GuiTimeSegmentState]) -> None:
        while self.segment_host.count():
            item = self.segment_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.segment_editors.clear()
        for index, state in enumerate(states):
            editor = SegmentEditor(index, state, self._handle_change, self._remove_segment, self.segment_panel)
            self.segment_host.addWidget(editor)
            self.segment_editors.append(editor)

    def _append_segment(self) -> None:
        states = [editor.collect_state() for editor in self.segment_editors]
        states.append(GuiTimeSegmentState(duration_min="0", point_count="0"))
        self._rebuild_segments(states)
        self._handle_change()

    def _remove_segment(self, index: int) -> None:
        states = [editor.collect_state() for editor in self.segment_editors]
        if len(states) <= 1:
            return
        del states[index]
        self._rebuild_segments(states)
        self._handle_change()

    def _count_values(self, text: str) -> int:
        try:
            return len(parse_float_list(text))
        except ValueError:
            return 0

    def _edit_manual_time_points(self) -> None:
        dialog = ManualPointDialog(title="编辑时间列表", text=self._manual_time_points_text, parent=self)
        if dialog.exec():
            self._manual_time_points_text = dialog.value()
            self._sync_visibility()
            self._handle_change()

    def _edit_manual_voltage_points(self) -> None:
        dialog = ManualPointDialog(title="编辑电压列表", text=self._manual_voltage_points_text, parent=self)
        if dialog.exec():
            self._manual_voltage_points_text = dialog.value()
            self.voltage_input_mode_combo.setCurrentIndex(self.voltage_input_mode_combo.findData(VoltageInputUiMode.MANUAL.value))
            self._sync_visibility()
            self._handle_change()

    def _edit_manual_time_points(self) -> None:
        dialog = GuidedManualPointDialog(title="编辑时间列表", text=self._manual_time_points_text, parent=self)
        if dialog.exec():
            self._manual_time_points_text = dialog.value()
            self._sync_visibility()
            self._handle_change()

    def _edit_manual_voltage_points(self) -> None:
        dialog = GuidedManualPointDialog(
            title="编辑电压列表",
            text=self._manual_voltage_points_text,
            is_voltage=True,
            direction=ProcessDirection(self.direction_combo.currentData()),
            parent=self,
        )
        if dialog.exec():
            self._manual_voltage_points_text = dialog.value()
            self.voltage_input_mode_combo.setCurrentIndex(self.voltage_input_mode_combo.findData(VoltageInputUiMode.MANUAL.value))
            self._sync_visibility()
            self._handle_change()

    def _refresh_badges(self) -> None:
        phase_kind = PhaseUiKind(self.phase_kind_combo.currentData())
        if phase_kind is PhaseUiKind.TIME_POINTS:
            mode = SamplingMode(self.time_mode_combo.currentData())
            if mode is SamplingMode.MANUAL:
                point_count = self._count_values(self._manual_time_points_text)
            elif mode is SamplingMode.FIXED:
                try:
                    total = float(self.fixed_total_duration_edit.text() or "0")
                    interval = float(self.fixed_interval_edit.text() or "0")
                    count = int(self.fixed_point_count_edit.text() or "0")
                except ValueError:
                    point_count = 0
                else:
                    point_count = count if self.fixed_mode_combo.currentData() == FixedTimeUiMode.POINT_COUNT.value else (int(total // interval) if interval > 0 else 0)
            else:
                point_count = sum(int(editor.point_count_edit.text() or "0") for editor in self.segment_editors)
        elif phase_kind is PhaseUiKind.VOLTAGE_POINTS:
            if self.voltage_input_mode_combo.currentData() == VoltageInputUiMode.MANUAL.value:
                point_count = self._count_values(self._manual_voltage_points_text)
            else:
                try:
                    from chi_generator.domain.models import VoltagePointConfig

                    point_count = len(
                        expand_voltage_range(
                            VoltagePointConfig(
                                start_v=float(self.voltage_start_edit.text() or "0"),
                                end_v=float(self.voltage_end_edit.text() or "0"),
                                step_v=float(self.voltage_step_edit.text() or "0"),
                            ),
                            ProcessDirection(self.direction_combo.currentData()),
                        )
                    )
                except ValueError:
                    point_count = 0
        else:
            point_count = 0
        eis_count = point_count if self.insert_eis_box.isChecked() and phase_kind is not PhaseUiKind.REST else 0
        self.point_count_label.setText(f"{point_count} 点 / {eis_count} 次 EIS")

    def _handle_smart_recommend(self) -> None:
        try:
            eis_s = float(self.manual_eis_edit.text() or "700")
            total_min = float(self.fixed_total_duration_edit.text() or "120")
        except ValueError:
            return
        self.time_mode_combo.setCurrentIndex(self.time_mode_combo.findData(SamplingMode.FIXED.value))
        self.fixed_mode_combo.setCurrentIndex(self.fixed_mode_combo.findData(FixedTimeUiMode.INTERVAL.value))
        interval, count = calculate_ctc_recommendation(total_min, eis_s)
        self.fixed_interval_edit.setText(f"{interval:g}")
        self.fixed_point_count_edit.setText(str(count))
        self._handle_change()

    def _sync_visibility(self) -> None:
        phase_kind = PhaseUiKind(self.phase_kind_combo.currentData())
        is_rest = phase_kind is PhaseUiKind.REST
        self.direction_combo.setVisible(not is_rest)
        self.current_mode_combo.setVisible(not is_rest)
        self.rate_edit.setVisible(not is_rest and self.current_mode_combo.currentData() == CurrentInputUiMode.RATE.value)
        self.current_edit.setVisible(not is_rest and self.current_mode_combo.currentData() == CurrentInputUiMode.ABSOLUTE.value)
        self.insert_eis_box.setVisible(not is_rest)
        self.common_row.setVisible(not is_rest)
        self.rest_row.setVisible(is_rest)

        is_time = phase_kind is PhaseUiKind.TIME_POINTS
        self.time_header_row.setVisible(is_time)
        self.fixed_row.setVisible(is_time and self.time_mode_combo.currentData() == SamplingMode.FIXED.value)
        self.fixed_interval_edit.setVisible(is_time and self.time_mode_combo.currentData() == SamplingMode.FIXED.value and self.fixed_mode_combo.currentData() == FixedTimeUiMode.INTERVAL.value)
        self.fixed_point_count_edit.setVisible(is_time and self.time_mode_combo.currentData() == SamplingMode.FIXED.value and self.fixed_mode_combo.currentData() == FixedTimeUiMode.POINT_COUNT.value)
        self.manual_time_wrap.setVisible(is_time and self.time_mode_combo.currentData() == SamplingMode.MANUAL.value)
        self.segment_panel.setVisible(is_time and self.time_mode_combo.currentData() == SamplingMode.SEGMENTED.value)

        is_voltage = phase_kind is PhaseUiKind.VOLTAGE_POINTS
        self.voltage_row.setVisible(is_voltage)
        self.manual_voltage_wrap.setVisible(is_voltage and self.voltage_input_mode_combo.currentData() == VoltageInputUiMode.MANUAL.value)
        self.voltage_start_edit.setVisible(is_voltage and self.voltage_input_mode_combo.currentData() == VoltageInputUiMode.RANGE.value)
        self.voltage_end_edit.setVisible(is_voltage and self.voltage_input_mode_combo.currentData() == VoltageInputUiMode.RANGE.value)
        self.voltage_step_edit.setVisible(is_voltage and self.voltage_input_mode_combo.currentData() == VoltageInputUiMode.RANGE.value)

        self.manual_time_status.setText(f"{self._count_values(self._manual_time_points_text)} 个值")
        self.manual_voltage_status.setText(f"{self._count_values(self._manual_voltage_points_text)} 个值")
        if is_time:
            self.phase_hint_label.setText("通过固定、分段或手动采样匹配放电过程的物理分区。")
        elif is_voltage:
            self.phase_hint_label.setText("电压工步可使用范围输入或手动列表，应对不可整除和非均匀取点。")
        else:
            self.phase_hint_label.setText("静置工步表示真正独立的静置阶段。")
        self._refresh_badges()

    def _handle_change(self) -> None:
        self._refresh_badges()
        self.on_change()

    def set_selected(self, selected: bool) -> None:
        self.select_box.setChecked(selected)

    def is_selected(self) -> bool:
        return self.select_box.isChecked()

    def set_order_state(self, index: int, total: int) -> None:
        self.index = index
        self.order_badge.setText(f"S{index:02d}")
        self.move_up_button.setEnabled(index > 1)
        self.move_down_button.setEnabled(index < total)
        self.delete_button.setEnabled(total > 1)

    def set_state(self, state: GuiPhaseState) -> None:
        def set_combo(combo: NoWheelComboBox, value: str) -> None:
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
        self.upper_voltage_edit.setText(state.upper_voltage_v)
        self.lower_voltage_edit.setText(state.lower_voltage_v)
        set_combo(self.time_mode_combo, state.sampling_mode.value)
        set_combo(self.time_basis_combo, state.time_basis_mode.value)
        self.manual_eis_edit.setText(state.manual_eis_duration_s)
        set_combo(self.fixed_mode_combo, state.fixed_mode.value)
        self.fixed_total_duration_edit.setText(state.fixed_total_duration_min)
        self.fixed_interval_edit.setText(state.fixed_interval_min)
        self.fixed_point_count_edit.setText(state.fixed_point_count)
        self._manual_time_points_text = state.manual_points_text
        self._rebuild_segments(state.segmented_points)
        set_combo(self.voltage_input_mode_combo, state.voltage_input_mode.value)
        self.voltage_start_edit.setText(state.voltage_start_v)
        self.voltage_end_edit.setText(state.voltage_end_v)
        self.voltage_step_edit.setText(state.voltage_step_v)
        self._manual_voltage_points_text = state.voltage_manual_points_text
        self.rest_duration_edit.setText(state.rest_duration_s)
        self._sync_visibility()

    def collect_state(self) -> GuiPhaseState:
        return GuiPhaseState.model_validate(
            {
                "label": self.label_edit.text() or self._default_label(),
                "phase_kind": self.phase_kind_combo.currentData(),
                "direction": self.direction_combo.currentData(),
                "current_mode": self.current_mode_combo.currentData(),
                "rate_c": self.rate_edit.text(),
                "current_a": self.current_edit.text(),
                "upper_voltage_v": self.upper_voltage_edit.text(),
                "lower_voltage_v": self.lower_voltage_edit.text(),
                "pre_wait_s": self.pre_wait_edit.text(),
                "sample_interval_s": self.sample_interval_edit.currentText(),
                "insert_eis_after_each_point": self.insert_eis_box.isChecked(),
                "sampling_mode": self.time_mode_combo.currentData(),
                "time_basis_mode": self.time_basis_combo.currentData(),
                "manual_points_text": self._manual_time_points_text,
                "manual_eis_duration_s": self.manual_eis_edit.text(),
                "fixed_mode": self.fixed_mode_combo.currentData(),
                "fixed_total_duration_min": self.fixed_total_duration_edit.text(),
                "fixed_interval_min": self.fixed_interval_edit.text(),
                "fixed_point_count": self.fixed_point_count_edit.text(),
                "segmented_points": [editor.collect_state() for editor in self.segment_editors],
                "voltage_input_mode": self.voltage_input_mode_combo.currentData(),
                "voltage_start_v": self.voltage_start_edit.text(),
                "voltage_end_v": self.voltage_end_edit.text(),
                "voltage_step_v": self.voltage_step_edit.text(),
                "voltage_manual_points_text": self._manual_voltage_points_text,
                "rest_duration_s": self.rest_duration_edit.text(),
            }
        )

    def _default_label(self) -> str:
        phase_kind = PhaseUiKind(self.phase_kind_combo.currentData())
        if phase_kind is PhaseUiKind.REST:
            return f"静置工步 {self.index}"
        direction_text = "放电" if self.direction_combo.currentData() == ProcessDirection.DISCHARGE.value else "充电"
        phase_text = "时间工步" if phase_kind is PhaseUiKind.TIME_POINTS else "电压工步"
        return f"{direction_text}{phase_text} {self.index}"


class LoopBlockWidget(QFrame):
    def __init__(
        self,
        index: int,
        state: GuiLoopState,
        *,
        on_change: Callable[[], None],
        on_move_up: Callable[["LoopBlockWidget"], None],
        on_move_down: Callable[["LoopBlockWidget"], None],
        on_delete: Callable[["LoopBlockWidget"], None],
        on_duplicate: Callable[["LoopBlockWidget"], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setProperty("workstepRow", True)
        self.index = index
        self.on_change = on_change
        self.on_move_up = on_move_up
        self.on_move_down = on_move_down
        self.on_delete = on_delete
        self.on_duplicate = on_duplicate
        self.phase_rows: list[WorkstepEditorRow] = []
        self._build_ui()
        self.set_state(state)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        header = QHBoxLayout()
        self.order_badge = QLabel(f"L{self.index:02d}")
        self.order_badge.setObjectName("stepBadge")
        self.label_edit = LineEdit(self)
        self.label_edit.setPlaceholderText("循环块名称")
        self.label_edit.textChanged.connect(self.on_change)
        self.repeat_count_edit = LineEdit(self)
        self.repeat_count_edit.setPlaceholderText("重复次数")
        self.repeat_count_edit.setMaximumWidth(88)
        self.repeat_count_edit.textChanged.connect(self.on_change)
        self.expand_button = PushButton(self)
        self.expand_button.clicked.connect(self._toggle_expanded)
        self.duplicate_button = PushButton(self)
        self.duplicate_button.setText("复制块")
        self.duplicate_button.clicked.connect(lambda: self.on_duplicate(self))
        self.move_up_button = PushButton(self)
        self.move_up_button.setText("上移")
        self.move_up_button.clicked.connect(lambda: self.on_move_up(self))
        self.move_down_button = PushButton(self)
        self.move_down_button.setText("下移")
        self.move_down_button.clicked.connect(lambda: self.on_move_down(self))
        self.delete_button = PushButton(self)
        self.delete_button.setText("删除")
        self.delete_button.clicked.connect(lambda: self.on_delete(self))
        header.addWidget(self.order_badge)
        header.addWidget(self.label_edit, 1)
        header.addWidget(QLabel("循环次数", self))
        header.addWidget(self.repeat_count_edit)
        header.addWidget(self.expand_button)
        header.addWidget(self.duplicate_button)
        header.addWidget(self.move_up_button)
        header.addWidget(self.move_down_button)
        header.addWidget(self.delete_button)
        root.addLayout(header)
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("phaseHint")
        root.addWidget(self.summary_label)
        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(12, 6, 0, 0)
        self.body_layout.setSpacing(8)
        root.addWidget(self.body)

    def _toggle_expanded(self) -> None:
        visible = not self.body.isVisible()
        self.body.setVisible(visible)
        self.expand_button.setText("折叠" if visible else "展开")
        self.on_change()

    def _refresh_summary(self) -> None:
        self.summary_label.setText(f"包含 {len(self.phase_rows)} 个工步，每轮展开 {len(self.phase_rows)} 个，当前重复次数 {self.repeat_count_edit.text() or '2'}。")

    def _sync_row_order(self) -> None:
        total = len(self.phase_rows)
        for index, row in enumerate(self.phase_rows, start=1):
            row.set_order_state(index, total)

    def _rebuild_rows(self, phases: list[GuiPhaseState]) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.phase_rows.clear()
        for index, phase in enumerate(phases, start=1):
            row = WorkstepEditorRow(
                index,
                phase,
                on_change=self.on_change,
                on_move_up=self._move_phase_up,
                on_move_down=self._move_phase_down,
                on_delete=self._delete_phase,
                parent=self.body,
            )
            row.select_box.setVisible(False)
            self.body_layout.addWidget(row)
            self.phase_rows.append(row)
        self._sync_row_order()
        self._refresh_summary()

    def _move_phase_up(self, row: WorkstepEditorRow) -> None:
        index = self.phase_rows.index(row)
        if index <= 0:
            return
        phases = [item.collect_state() for item in self.phase_rows]
        phases[index - 1], phases[index] = phases[index], phases[index - 1]
        self._rebuild_rows(phases)
        self.on_change()

    def _move_phase_down(self, row: WorkstepEditorRow) -> None:
        index = self.phase_rows.index(row)
        if index >= len(self.phase_rows) - 1:
            return
        phases = [item.collect_state() for item in self.phase_rows]
        phases[index + 1], phases[index] = phases[index], phases[index + 1]
        self._rebuild_rows(phases)
        self.on_change()

    def _delete_phase(self, row: WorkstepEditorRow) -> None:
        if len(self.phase_rows) <= 1:
            return
        phases = [item.collect_state() for item in self.phase_rows if item is not row]
        self._rebuild_rows(phases)
        self.on_change()

    def set_order_state(self, index: int, total: int) -> None:
        self.index = index
        self.order_badge.setText(f"L{index:02d}")
        self.move_up_button.setEnabled(index > 1)
        self.move_down_button.setEnabled(index < total)
        self.delete_button.setEnabled(total > 1)

    def set_state(self, state: GuiLoopState) -> None:
        self.label_edit.setText(state.label)
        self.repeat_count_edit.setText(str(state.repeat_count))
        self.body.setVisible(state.expanded)
        self.expand_button.setText("折叠" if state.expanded else "展开")
        self._rebuild_rows(state.phases)

    def collect_state(self) -> GuiLoopState:
        return GuiLoopState(
            label=self.label_edit.text() or f"循环块 {self.index}",
            repeat_count=int(self.repeat_count_edit.text() or "2"),
            expanded=self.body.isVisible(),
            phases=[row.collect_state() for row in self.phase_rows],
        )


class IssueListWidget(ListWidget):
    _code_map = {
        "dense_eis_low_frequency": "低频端设置为 0.01 Hz，判定为高风险密集取点。",
        "long_single_eis_duration": "当前单次 EIS 持续时间较长。",
        "interrupted_progress": "EIS 插入过于频繁，会明显打断恒流轨迹。",
        "high_compensation_total": "中断补偿累计时间较大，会拉长后续恒流历时。",
        "frequent_direction_switches": "工步切换充放电方向较频繁，请确认流程设计。",
        "rest_dominates_sequence": "静置总时长超过电化学工作时长，请确认是否符合预期。",
        "soc_depletion_risk": "SoC 仿真显示在全部 EIS 完成前可能已经耗尽。",
        "ctc_enabled": "已启用等效容量补偿。",
        "missing_phases": "至少需要一个工步。",
        "phase_invalid": "工步参数无效。",
        "missing_pulse": "脉冲模式缺少脉冲参数。",
        "ui.refresh": "界面预览刷新失败。",
    }

    _hint_map = {
        "dense_eis_low_frequency": "风险预估按长时低频 EIS 处理。",
        "long_single_eis_duration": "当前估算的单次扫描时间较长。",
        "interrupted_progress": "建议降低取点密度，或只在关键点插入 EIS。",
        "high_compensation_total": "建议检查中断补偿模式是否过密。",
        "soc_depletion_risk": "采样看板中的红点表示预测会丢失的点位。",
        "ctc_enabled": "适用于需要锁定总等效放电量的测试。",
    }

    _risk_map = {
        RiskLevel.BLOCKING: "阻断",
        RiskLevel.HIGH: "强警告",
        RiskLevel.MEDIUM: "警告",
        RiskLevel.LOW: "提示",
        None: "",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWordWrap(True)

    def _format_issue(self, issue: ValidationIssue) -> str:
        severity_map = {Severity.ERROR: "错误", Severity.WARNING: "警告", Severity.INFO: "提示"}
        field_map = {"impedance_defaults.low_frequency_hz": "阻抗低频", "phases": "工步", "pulse": "脉冲参数"}
        message = self._code_map.get(issue.code, issue.message)
        if issue.code == "phase_invalid" and issue.message:
            message = issue.message
        hint = self._hint_map.get(issue.code, issue.hint)
        field = field_map.get(issue.field or "", issue.field or "-")
        headline = f"[{severity_map[issue.severity]}] {field}: {message}"
        risk_prefix = self._risk_map.get(issue.risk_level, "")
        if risk_prefix:
            headline = f"[{risk_prefix}] {headline}"
        if hint:
            headline += f"\n提示：{hint}"
        return headline

    def set_issues(self, issues: list[ValidationIssue]) -> None:
        self.clear()
        if not issues:
            self.addItem(QListWidgetItem("当前没有警告或错误。"))
            return
        for issue in issues:
            item = QListWidgetItem(self._format_issue(issue))
            if issue.severity is Severity.ERROR:
                item.setForeground(Qt.GlobalColor.red)
            elif issue.risk_level is RiskLevel.HIGH:
                item.setForeground(Qt.GlobalColor.darkYellow)
            elif issue.severity is Severity.WARNING:
                item.setForeground(Qt.GlobalColor.darkYellow)
            else:
                item.setForeground(Qt.GlobalColor.darkCyan)
            self.addItem(item)


class GuidedManualPointDialog(QDialog):
    def __init__(
        self,
        *,
        title: str,
        text: str,
        is_voltage: bool = False,
        direction: ProcessDirection | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._is_voltage = is_voltage
        self._direction = direction
        self.setWindowTitle(title)
        self.resize(480, 360)
        self.setStyleSheet(
            "QDialog { background-color: #f3f5f7; }"
            "QLabel { color: #5f6b7a; }"
            "QDialogButtonBox QPushButton { min-width: 72px; color: #1d2329; }"
            "QDialogButtonBox QPushButton:disabled { color: #1d2329; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint_parts = ["支持粘贴逗号、空格或换行分隔的数值。时间列表输入累计分钟，电压列表输入伏特。"]
        if is_voltage and direction is ProcessDirection.DISCHARGE:
            hint_parts.append("当前工步为放电，建议按从高到低输入，例如 3.20 3.05 2.92 2.80。")
        elif is_voltage and direction is ProcessDirection.CHARGE:
            hint_parts.append("当前工步为充电，建议按从低到高输入，例如 2.80 2.92 3.05 3.20。")
        self.hint_label = QLabel("\n".join(hint_parts), self)
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        self.editor = QPlainTextEdit(self)
        self.editor.setPlainText(text)
        self.editor.setPlaceholderText("3.20\n3.05\n2.92\n2.80" if is_voltage else "10\n25\n40\n60")
        self.editor.setStyleSheet(
            "QPlainTextEdit { background-color: #f7f8fa; color: #1d2329; border: 1px solid #b8c0cc; border-radius: 8px; padding: 8px; selection-background-color: #cfd6df; selection-color: #1d2329; }"
            "QPlainTextEdit:focus { border: 1px solid #98a2b3; }"
        )
        font = self.editor.font()
        font.setFamily(fixed_font_family())
        self.editor.setFont(font)
        layout.addWidget(self.editor, 1)

        self.stats_label = QLabel(self)
        self.stats_label.setWordWrap(True)
        layout.addWidget(self.stats_label)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.editor.textChanged.connect(self._refresh_stats)
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        values = parse_float_list(self.editor.toPlainText())
        if not values:
            self.stats_label.setText("当前未识别到有效数值。")
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
            return

        messages = [f"已识别 {len(values)} 个值，首末值 {values[0]:g} -> {values[-1]:g}。"]
        ok_enabled = True
        if self._is_voltage and len(values) >= 2:
            deltas = [current - previous for previous, current in zip(values, values[1:])]
            strictly_up = all(delta > 0 for delta in deltas)
            strictly_down = all(delta < 0 for delta in deltas)
            if self._direction is ProcessDirection.DISCHARGE:
                if strictly_down:
                    messages.append("方向检查：符合放电降序。")
                elif strictly_up:
                    messages.append("方向检查：当前为升序，生成时会按放电方向处理。")
                else:
                    messages.append("方向检查：存在非单调电压点，请整理后再保存。")
                    ok_enabled = False
            elif self._direction is ProcessDirection.CHARGE:
                if strictly_up:
                    messages.append("方向检查：符合充电升序。")
                elif strictly_down:
                    messages.append("方向检查：当前为降序，生成时会按充电方向处理。")
                else:
                    messages.append("方向检查：存在非单调电压点，请整理后再保存。")
                    ok_enabled = False
        self.stats_label.setText("\n".join(messages))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok_enabled)

    def value(self) -> str:
        return self.editor.toPlainText().strip()


PhaseEditor = WorkstepEditorRow
WorkstepRow = WorkstepEditorRow


__all__ = [
    "Card",
    "IssueListWidget",
    "LoopBlockWidget",
    "LoopCountDialog",
    "NoWheelComboBox",
    "PresetComboBox",
    "PhaseEditor",
    "ScriptEditor",
    "ScriptOutputPanel",
    "WorkstepRow",
    "WorkstepEditorRow",
    "fixed_font_family",
]
