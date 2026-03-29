"""Main application window."""

from __future__ import annotations

from importlib import resources

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QPlainTextEdit,
)

from .adapters import DomainValidationPreviewAdapter
from .models import CurrentInputMode, PreviewArtifact, ScriptFormState, ScriptVariant, TechniqueMode, WorkflowMode
from .widgets import Card, IssueListWidget, ScriptOutputPanel


class MainWindow(QMainWindow):
    """PyQt6 desktop UI for CHI in-situ script preparation."""

    def __init__(self, backend: DomainValidationPreviewAdapter, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._backend = backend
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120)
        self._refresh_timer.timeout.connect(self.refresh_preview)
        self._build_ui()
        self._connect_signals()
        self._apply_defaults()
        self.refresh_preview()

    def _build_ui(self) -> None:
        self.setWindowTitle("辰华（CHI）原位阻抗脚本生成器")
        self.resize(1520, 920)
        self.setMinimumSize(1280, 800)

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        self.left_panel = self._build_left_panel()
        self.right_panel = self._build_right_panel()
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        self.statusBar().showMessage("就绪")
        self._apply_stylesheet()

    def _build_left_panel(self) -> QWidget:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self.left_layout = QVBoxLayout(content)
        self.left_layout.setContentsMargins(12, 12, 12, 12)
        self.left_layout.setSpacing(12)

        self._build_general_card()
        self._build_workflow_card()
        self._build_technique_card()
        self._build_actions_card()

        self.left_layout.addStretch(1)
        scroll.setWidget(content)
        root_layout.addWidget(scroll)
        return root

    def _build_general_card(self) -> None:
        card = Card("基础参数")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.file_prefix_edit = QLineEdit()
        self.file_prefix_edit.setPlaceholderText("例如 OCVEIA")
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("可选备注")
        self.eh_spin = self._double_spin(-100.0, 100.0, 0.01, 4)
        self.el_spin = self._double_spin(-100.0, 100.0, 0.01, 4)
        self.cl_spin = QSpinBox()
        self.cl_spin.setRange(1, 999)
        self.active_mass_spin = self._double_spin(0.0, 10000.0, 0.0001, 6)
        self.specific_capacity_spin = self._double_spin(0.0, 10000.0, 0.1, 3)

        self.current_mode_combo = QComboBox()
        self.current_mode_combo.addItem("直接输入电流", CurrentInputMode.direct_current)
        self.current_mode_combo.addItem("输入 1C 电流", CurrentInputMode.one_c_reference)
        self.current_mode_combo.addItem("输入倍率电流并反推 1C", CurrentInputMode.rate_reference)
        self.direct_current_spin = self._double_spin(0.0, 1000.0, 0.0000001, 7)
        self.one_c_current_spin = self._double_spin(0.0, 1000.0, 0.0000001, 7)
        self.reference_rate_spin = self._double_spin(0.0, 1000.0, 0.1, 3)
        self.reference_current_spin = self._double_spin(0.0, 1000.0, 0.0000001, 7)

        form.addRow("文件前缀", self.file_prefix_edit)
        form.addRow("备注", self.note_edit)
        form.addRow("eh / 上限 V", self.eh_spin)
        form.addRow("el / 下限 V", self.el_spin)
        form.addRow("cl", self.cl_spin)
        form.addRow("活性物质量 mg", self.active_mass_spin)
        form.addRow("比容量 mAh/g", self.specific_capacity_spin)
        form.addRow("输入模式", self.current_mode_combo)
        form.addRow("直接电流 A", self.direct_current_spin)
        form.addRow("1C 电流 A", self.one_c_current_spin)
        form.addRow("倍率 C", self.reference_rate_spin)
        form.addRow("该倍率电流 A", self.reference_current_spin)
        card.content_layout.addLayout(form)
        self.left_layout.addWidget(card)

    def _build_workflow_card(self) -> None:
        card = Card("取点模式")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.workflow_combo = QComboBox()
        self.workflow_combo.addItem("固定电压点", WorkflowMode.fixed_voltage)
        self.workflow_combo.addItem("固定时间点", WorkflowMode.fixed_time)
        self.workflow_combo.addItem("分段均匀时间点", WorkflowMode.segmented_time)
        self.workflow_combo.addItem("活化 + 主过程", WorkflowMode.activation_main)

        self.workflow_stack = QStackedWidget()
        self.fixed_voltage_edit = self._text_edit("3.2, 3.0, 2.9, 2.7, 2.5")
        self.fixed_time_edit = self._text_edit("2, 6, 10, 14, 18")
        self.segmented_time_edit = self._text_edit("2, 6, 10, 14, 18\n30, 50, 70, 90")
        self.activation_edit = self._text_edit("0.0000865, 120\n0.000040136, 240")
        self.main_edit = self._text_edit("0.0000865, 1800\n0.0000865, 1800")

        self.workflow_stack.addWidget(self.fixed_voltage_edit)
        self.workflow_stack.addWidget(self.fixed_time_edit)
        self.workflow_stack.addWidget(self.segmented_time_edit)
        activation_block = QWidget()
        activation_layout = QVBoxLayout(activation_block)
        activation_layout.setContentsMargins(0, 0, 0, 0)
        activation_layout.setSpacing(8)
        activation_layout.addWidget(QLabel("活化段"))
        activation_layout.addWidget(self.activation_edit)
        activation_layout.addWidget(QLabel("主过程"))
        activation_layout.addWidget(self.main_edit)
        self.workflow_stack.addWidget(activation_block)

        form.addRow("工作流", self.workflow_combo)
        form.addRow("步骤定义", self.workflow_stack)
        card.content_layout.addLayout(form)
        self.left_layout.addWidget(card)

    def _build_technique_card(self) -> None:
        card = Card("技术细节")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.technique_combo = QComboBox()
        self.technique_combo.addItem("IMP", TechniqueMode.imp)
        self.technique_combo.addItem("CP", TechniqueMode.cp)
        self.technique_combo.addItem("ISTEP", TechniqueMode.istep)
        self.technique_combo.addItem("delay", TechniqueMode.delay)

        self.output_variant_combo = QComboBox()
        self.output_variant_combo.addItem("注释版", ScriptVariant.commented)
        self.output_variant_combo.addItem("极简版", ScriptVariant.minimal)

        self.ocv_enabled_check = QCheckBox("启用 OCV")
        self.ocv_enabled_check.setChecked(True)
        self.ocv_duration_spin = self._double_spin(0.0, 100000.0, 1.0, 2)
        self.ocv_sample_interval_spin = self._double_spin(0.0, 1000.0, 0.1, 2)
        self.imp_insertions_spin = QSpinBox()
        self.imp_insertions_spin.setRange(0, 999)
        self.imp_fh_spin = self._double_spin(0.0, 100000000.0, 1.0, 3)
        self.imp_fl_spin = self._double_spin(0.0, 1000000.0, 0.001, 3)
        self.points_per_decade_spin = QSpinBox()
        self.points_per_decade_spin.setRange(1, 999)
        self.imp_amp_spin = self._double_spin(0.0, 1000.0, 0.0001, 6)
        self.imp_quiet_spin = self._double_spin(0.0, 100000.0, 1.0, 2)
        self.use_ocv_check = QCheckBox("Use Open Circuit E as Init E")
        self.use_ocv_check.setChecked(True)
        self.delay_spin = self._double_spin(0.0, 100000.0, 1.0, 2)

        self.cp_ic_spin = self._double_spin(-1000.0, 1000.0, 0.0000001, 7)
        self.cp_ia_spin = self._double_spin(-1000.0, 1000.0, 0.0000001, 7)
        self.cp_eh_spin = self._double_spin(-1000.0, 1000.0, 0.01, 4)
        self.cp_el_spin = self._double_spin(-1000.0, 1000.0, 0.01, 4)
        self.cp_tc_spin = self._double_spin(0.0, 100000.0, 0.1, 2)
        self.cp_ta_spin = self._double_spin(0.0, 100000.0, 0.1, 2)
        self.cp_cl_spin = QSpinBox()
        self.cp_cl_spin.setRange(0, 999)
        self.cp_priority_combo = QComboBox()
        self.cp_priority_combo.addItem("prioe", "prioe")
        self.cp_priority_combo.addItem("priot", "priot")

        form.addRow("输出", self.output_variant_combo)
        form.addRow("技术", self.technique_combo)
        form.addRow("OCV 启用", self.ocv_enabled_check)
        form.addRow("OCV duration s", self.ocv_duration_spin)
        form.addRow("OCV sample interval s", self.ocv_sample_interval_spin)
        form.addRow("IMP 插入次数", self.imp_insertions_spin)
        form.addRow("IMP fh Hz", self.imp_fh_spin)
        form.addRow("IMP fl Hz", self.imp_fl_spin)
        form.addRow("points/decade", self.points_per_decade_spin)
        form.addRow("IMP amp V", self.imp_amp_spin)
        form.addRow("IMP qt s", self.imp_quiet_spin)
        form.addRow("Init E", self.use_ocv_check)
        form.addRow("delay s", self.delay_spin)
        form.addRow("CP ic A", self.cp_ic_spin)
        form.addRow("CP ia A", self.cp_ia_spin)
        form.addRow("CP eh V", self.cp_eh_spin)
        form.addRow("CP el V", self.cp_el_spin)
        form.addRow("CP tc s", self.cp_tc_spin)
        form.addRow("CP ta s", self.cp_ta_spin)
        form.addRow("CP cl", self.cp_cl_spin)
        form.addRow("CP 优先级", self.cp_priority_combo)
        card.content_layout.addLayout(form)
        self.left_layout.addWidget(card)

    def _build_actions_card(self) -> None:
        card = Card("操作")
        row = QHBoxLayout()
        self.run_refresh_button = QPushButton("生成预览")
        self.copy_button = QPushButton("复制当前脚本")
        row.addWidget(self.run_refresh_button)
        row.addWidget(self.copy_button)
        row.addStretch(1)
        card.content_layout.addLayout(row)
        self.left_layout.addWidget(card)

    def _build_right_panel(self) -> QWidget:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.issue_card = Card("告警")
        self.issue_list = IssueListWidget()
        self.issue_card.content_layout.addWidget(self.issue_list)

        self.preview_card = Card("脚本预览")
        self.output_panel = ScriptOutputPanel()
        self.preview_card.content_layout.addWidget(self.output_panel)

        layout.addWidget(self.issue_card, 1)
        layout.addWidget(self.preview_card, 2)
        return root

    def _text_edit(self, placeholder: str) -> QPlainTextEdit:
        edit = QPlainTextEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMinimumHeight(110)
        return edit

    def _double_spin(self, minimum: float, maximum: float, step: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setSingleStep(step)
        spin.setAccelerated(True)
        return spin

    def _connect_signals(self) -> None:
        widgets = [
            self.file_prefix_edit,
            self.note_edit,
            self.eh_spin,
            self.el_spin,
            self.cl_spin,
            self.active_mass_spin,
            self.specific_capacity_spin,
            self.current_mode_combo,
            self.direct_current_spin,
            self.one_c_current_spin,
            self.reference_rate_spin,
            self.reference_current_spin,
            self.workflow_combo,
            self.technique_combo,
            self.output_variant_combo,
            self.ocv_enabled_check,
            self.ocv_duration_spin,
            self.ocv_sample_interval_spin,
            self.imp_insertions_spin,
            self.imp_fh_spin,
            self.imp_fl_spin,
            self.points_per_decade_spin,
            self.imp_amp_spin,
            self.imp_quiet_spin,
            self.use_ocv_check,
            self.delay_spin,
            self.cp_ic_spin,
            self.cp_ia_spin,
            self.cp_eh_spin,
            self.cp_el_spin,
            self.cp_tc_spin,
            self.cp_ta_spin,
            self.cp_cl_spin,
            self.cp_priority_combo,
        ]
        for widget in widgets:
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self.schedule_refresh)
            elif hasattr(widget, "currentIndexChanged"):
                widget.currentIndexChanged.connect(self.schedule_refresh)
            elif hasattr(widget, "stateChanged"):
                widget.stateChanged.connect(self.schedule_refresh)
            elif hasattr(widget, "textChanged"):
                widget.textChanged.connect(self.schedule_refresh)

        self.workflow_combo.currentIndexChanged.connect(self._update_workflow_stack)
        self.current_mode_combo.currentIndexChanged.connect(self._update_current_mode_fields)
        self.run_refresh_button.clicked.connect(self.refresh_preview)
        self.copy_button.clicked.connect(self.copy_current_script)

        for editor in [
            self.fixed_voltage_edit,
            self.fixed_time_edit,
            self.segmented_time_edit,
            self.activation_edit,
            self.main_edit,
        ]:
            editor.textChanged.connect(self.schedule_refresh)

    def _apply_defaults(self) -> None:
        self._update_workflow_stack()
        self._update_current_mode_fields()

    def _apply_stylesheet(self) -> None:
        try:
            stylesheet = resources.files("opeis_master.ui").joinpath("theme.qss").read_text(encoding="utf-8")
        except (FileNotFoundError, ModuleNotFoundError, OSError):
            stylesheet = ""
        app = QApplication.instance()
        if app is not None:
            app.setStyle("Fusion")
            app.setStyleSheet(stylesheet)

    def _update_workflow_stack(self, *_: object) -> None:
        self.workflow_stack.setCurrentIndex(self.workflow_combo.currentIndex())
        self.schedule_refresh()

    def _update_current_mode_fields(self, *_: object) -> None:
        mode = self.current_mode_combo.currentData()
        self.direct_current_spin.setEnabled(mode == CurrentInputMode.direct_current)
        self.one_c_current_spin.setEnabled(mode == CurrentInputMode.one_c_reference)
        self.reference_rate_spin.setEnabled(mode == CurrentInputMode.rate_reference)
        self.reference_current_spin.setEnabled(mode == CurrentInputMode.rate_reference)
        self.schedule_refresh()

    def schedule_refresh(self, *_: object) -> None:
        self._refresh_timer.start()

    def _collect_state(self) -> ScriptFormState:
        return ScriptFormState(
            workflow=self.workflow_combo.currentData(),
            technique=self.technique_combo.currentData(),
            output_variant=self.output_variant_combo.currentData(),
            current_mode=self.current_mode_combo.currentData(),
            active_mass_mg=self.active_mass_spin.value(),
            specific_capacity_mah_g=self.specific_capacity_spin.value(),
            direct_current_a=self.direct_current_spin.value(),
            one_c_current_a=self.one_c_current_spin.value(),
            reference_rate_c=self.reference_rate_spin.value(),
            reference_rate_current_a=self.reference_current_spin.value(),
            eh_v=self.eh_spin.value(),
            el_v=self.el_spin.value(),
            cl=self.cl_spin.value(),
            imp_fh_hz=self.imp_fh_spin.value(),
            imp_fl_hz=self.imp_fl_spin.value(),
            points_per_decade=self.points_per_decade_spin.value(),
            imp_amp_v=self.imp_amp_spin.value(),
            imp_quiet_time_s=self.imp_quiet_spin.value(),
            imp_insertions=self.imp_insertions_spin.value(),
            ocv_enabled=self.ocv_enabled_check.isChecked(),
            ocv_duration_s=self.ocv_duration_spin.value(),
            ocv_sample_interval_s=self.ocv_sample_interval_spin.value(),
            use_ocv_as_init_e=self.use_ocv_check.isChecked(),
            delay_s=self.delay_spin.value(),
            file_prefix=self.file_prefix_edit.text().strip() or "OCVEIA",
            note=self.note_edit.text().strip(),
            fixed_voltage_points_text=self.fixed_voltage_edit.toPlainText(),
            fixed_time_points_text=self.fixed_time_edit.toPlainText(),
            segmented_time_points_text=self.segmented_time_edit.toPlainText(),
            activation_steps_text=self.activation_edit.toPlainText(),
            main_steps_text=self.main_edit.toPlainText(),
            cp_ic_a=self.cp_ic_spin.value(),
            cp_ia_a=self.cp_ia_spin.value(),
            cp_eh_v=self.cp_eh_spin.value(),
            cp_el_v=self.cp_el_spin.value(),
            cp_tc_s=self.cp_tc_spin.value(),
            cp_ta_s=self.cp_ta_spin.value(),
            cp_cl=self.cp_cl_spin.value(),
            cp_priority=self.cp_priority_combo.currentData(),
        )

    def refresh_preview(self, *_: object) -> None:
        state = self._collect_state()
        artifact = self._backend.preview(state)
        self._render_artifact(artifact)
        self.statusBar().showMessage(
            f"工作流 {state.workflow.value} / 技术 {state.technique.value} / "
            f"错误 {len(artifact.validation.errors)} / 警告 {len(artifact.validation.warnings)}"
        )

    def _render_artifact(self, artifact: PreviewArtifact) -> None:
        self.issue_list.set_issues([*artifact.validation.errors, *artifact.validation.warnings])
        self.output_panel.set_scripts(
            artifact.commented_script,
            artifact.minimal_script,
            artifact.summary,
            artifact.preview_ready,
        )

    def copy_current_script(self, *_: object) -> None:
        current_text = self.output_panel.comment_editor.toPlainText()
        if self.output_panel.tabs.currentIndex() == 1:
            current_text = self.output_panel.minimal_editor.toPlainText()
        if not current_text.strip():
            return
        QApplication.clipboard().setText(current_text)
