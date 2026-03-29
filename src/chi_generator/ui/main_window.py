"""Main application window for the CHI in-situ EIS generator."""

from __future__ import annotations

from pathlib import Path
import re

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from chi_generator.domain.models import ScriptBundle, SequenceScriptBundle, Severity, ValidationIssue
from chi_generator.ui.adapters import GuiBackend
from chi_generator.ui.models import CurrentInputUiMode, GuiPhaseState, GuiState, PhaseUiKind, RelaxationUiMode, WorkspaceMode
from chi_generator.ui.presets import PresetFileService
from chi_generator.ui.widgets import Card, IssueListWidget, NoWheelComboBox, PresetComboBox, ScriptOutputPanel, WorkstepEditorRow


class MainWindow(QMainWindow):
    """PyQt6 desktop UI for sequence and pulse script generation."""

    def __init__(
        self,
        service: object | None = None,
        parent: QWidget | None = None,
        preset_service: PresetFileService | None = None,
    ) -> None:
        super().__init__(parent)
        self._backend = GuiBackend(service=service)
        self._preset_service = preset_service or PresetFileService()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(90)
        self._refresh_timer.timeout.connect(self.refresh_preview)
        self._updating_ui = False
        self._last_bundle: ScriptBundle | None = None
        self._current_preset_path: Path | None = None
        self.phase_editors: list[WorkstepEditorRow] = []
        self._build_ui()
        self._connect_signals()
        self._apply_defaults()
        self._update_recent_presets()
        self.refresh_preview()

    def _build_ui(self) -> None:
        self.setWindowTitle("辰华原位阻抗脚本生成终端")
        self.resize(1560, 940)
        self.setMinimumSize(1320, 840)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

        self.left_panel = self._build_left_panel()
        self.right_panel = self._build_right_panel()
        self.right_panel.setMaximumWidth(540)
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1120, 420])

        self.statusBar().showMessage("就绪")
        self._apply_styles()

    def _build_left_panel(self) -> QWidget:
        root = QWidget(self)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(root)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        body = QWidget(scroll)
        self.left_layout = QVBoxLayout(body)
        self.left_layout.setContentsMargins(18, 18, 18, 18)
        self.left_layout.setSpacing(14)

        self.workspace_card = self._build_workspace_card()
        self.project_card = self._build_project_card()
        self.battery_card = self._build_battery_card()
        self.workstep_card = self._build_workstep_card()
        self.pulse_card = self._build_pulse_card()
        self.impedance_card = self._build_impedance_card()
        self.sequence_card = self.workstep_card

        for card in (
            self.workspace_card,
            self.project_card,
            self.battery_card,
            self.workstep_card,
            self.pulse_card,
            self.impedance_card,
        ):
            self.left_layout.addWidget(card)
        self.left_layout.addStretch(1)

        scroll.setWidget(body)
        layout.addWidget(scroll)
        return root

    def _build_right_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        self.status_card = Card("辰华原位阻抗脚本生成终端", panel)
        hero = QFrame(self.status_card)
        hero.setProperty("hero", True)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(10)

        self.workspace_mode_label = QLabel("辰华原位阻抗脚本生成终端", hero)
        self.workspace_mode_label.setObjectName("heroKicker")
        self.workspace_headline = QLabel("交替工步在同一条工作流里完成", hero)
        self.workspace_headline.setObjectName("heroTitle")
        self.workspace_copy = QLabel("统一从工步表格编辑，模板只负责快速起手。", hero)
        self.workspace_copy.setObjectName("heroBody")
        self.current_basis_label = QLabel("电流基准", hero)
        self.current_basis_label.setObjectName("metaLabel")
        self.current_preview_label = QLabel("-", hero)
        self.current_preview_label.setObjectName("metricText")
        hero_layout.addWidget(self.workspace_mode_label)
        hero_layout.addWidget(self.workspace_headline)
        hero_layout.addWidget(self.workspace_copy)
        hero_layout.addWidget(self.current_basis_label)
        hero_layout.addWidget(self.current_preview_label)
        self.status_card.content_layout.addWidget(hero)
        layout.addWidget(self.status_card)

        self.issue_card = Card("Warnings & Errors", panel)
        self.issue_list = IssueListWidget(self.issue_card)
        self.issue_card.content_layout.addWidget(self.issue_list)
        layout.addWidget(self.issue_card, 1)

        self.preview_card = Card("Script Preview", panel)
        self.output_panel = ScriptOutputPanel(self.preview_card)
        self.preview_card.content_layout.addWidget(self.output_panel)
        layout.addWidget(self.preview_card, 2)
        return panel

    def _build_workspace_card(self) -> Card:
        card = Card("Workspace", self)

        hero = QFrame(card)
        hero.setProperty("hero", True)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        branding = QVBoxLayout()
        branding.setSpacing(2)
        kicker = QLabel("辰华原位阻抗脚本生成终端", hero)
        kicker.setObjectName("heroKicker")
        title = QLabel("可切换的序列编辑器", hero)
        title.setObjectName("heroTitle")
        body = QLabel("工步类型在行内切换；上方只保留一个主新增动作，模板用于快速填充。", hero)
        body.setObjectName("heroBody")
        branding.addWidget(kicker)
        branding.addWidget(title)
        branding.addWidget(body)

        mode_box = QVBoxLayout()
        mode_box.setSpacing(4)
        mode_label = QLabel("工作区模式", hero)
        mode_label.setObjectName("metaLabel")
        self.mode_combo = NoWheelComboBox(hero)
        self.mode_combo.addItem("工步序列", WorkspaceMode.SEQUENCE.value)
        self.mode_combo.addItem("Pulse", WorkspaceMode.PULSE.value)
        self.mode_combo.setMinimumWidth(180)
        self._scenario = self.mode_combo
        mode_box.addWidget(mode_label)
        mode_box.addWidget(self.mode_combo)

        top_row.addLayout(branding, 1)
        top_row.addLayout(mode_box)
        hero_layout.addLayout(top_row)

        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        self.new_preset_button = QPushButton("新建预设", hero)
        self.open_preset_button = QPushButton("打开", hero)
        self.save_preset_button = QPushButton("保存", hero)
        self.save_as_preset_button = QPushButton("另存为", hero)
        self.recent_presets_combo = NoWheelComboBox(hero)
        self.recent_presets_combo.setMinimumWidth(220)
        self.recent_preset_combo = self.recent_presets_combo
        self.recent_presets_combo.addItem("最近预设", "")
        for button in (
            self.new_preset_button,
            self.open_preset_button,
            self.save_preset_button,
            self.save_as_preset_button,
        ):
            button.setObjectName("ghostButton")
        preset_row.addWidget(self.new_preset_button)
        preset_row.addWidget(self.open_preset_button)
        preset_row.addWidget(self.save_preset_button)
        preset_row.addWidget(self.save_as_preset_button)
        preset_row.addStretch(1)
        preset_row.addWidget(self.recent_presets_combo)
        hero_layout.addLayout(preset_row)

        card.content_layout.addWidget(hero)
        return card

    def _build_project_card(self) -> Card:
        card = Card("Project", self)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scheme_name_edit = self._line_edit("方案名称")
        self.file_prefix_edit = self._line_edit("文件前缀")
        self.export_dir_edit = self._line_edit("导出目录")
        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        export_row.addWidget(self.export_dir_edit, 1)
        self.export_dir_browse_button = QPushButton("浏览", card)
        self.export_dir_browse_button.setObjectName("ghostButton")
        export_row.addWidget(self.export_dir_browse_button)
        export_wrap = QWidget(card)
        export_wrap.setLayout(export_row)

        form.addRow("方案名称", self.scheme_name_edit)
        form.addRow("命名前缀", self.file_prefix_edit)
        form.addRow("导出目录", export_wrap)
        card.content_layout.addLayout(form)
        return card

    def _build_battery_card(self) -> Card:
        card = Card("Battery & Current", self)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.active_material_edit = self._line_edit("活性物质量 / mg")
        self.theoretical_capacity_edit = self._line_edit("理论容量 / mAh/g")
        self.current_basis_value = QLabel("按活性物质量换算 1C 电流", card)
        self.current_basis_value.setObjectName("inlineValue")
        self.current_operating_value = QLabel("-", card)
        self.current_operating_value.setObjectName("accentValue")

        form.addRow("活性物质量 / mg", self.active_material_edit)
        form.addRow("理论容量 / mAh/g", self.theoretical_capacity_edit)
        form.addRow("电流基准", self.current_basis_value)
        form.addRow("当前工作电流", self.current_operating_value)
        card.content_layout.addLayout(form)
        return card

    def _build_workstep_card(self) -> Card:
        card = Card("Worksteps", self)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.workstep_count_pill = self._metric_pill("1 个工步")
        self.total_points_pill = self._metric_pill("24 点")
        self.total_eis_pill = self._metric_pill("24 EIS")
        header.addStretch(1)
        header.addWidget(self.workstep_count_pill)
        header.addWidget(self.total_points_pill)
        header.addWidget(self.total_eis_pill)
        card.content_layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.add_workstep_button = QPushButton("添加工步", card)
        self.add_workstep_button.setObjectName("primaryButton")
        self.time_template_button = QPushButton("固定时间点模板", card)
        self.voltage_template_button = QPushButton("固定电压点模板", card)
        self.activation_template_button = QPushButton("充放交替模板", card)
        for button in (self.time_template_button, self.voltage_template_button, self.activation_template_button):
            button.setObjectName("ghostButton")
        toolbar.addWidget(self.add_workstep_button)
        toolbar.addWidget(self.time_template_button)
        toolbar.addWidget(self.voltage_template_button)
        toolbar.addWidget(self.activation_template_button)
        toolbar.addStretch(1)
        card.content_layout.addLayout(toolbar)

        self.workstep_intro_label = QLabel(
            "统一从默认工步开始，类型可在每一行内切换；模板只负责快速起手，不再和新增入口重复。",
            card,
        )
        self.workstep_intro_label.setObjectName("mutedLabel")
        self.workstep_intro_label.setWordWrap(True)
        card.content_layout.addWidget(self.workstep_intro_label)

        hidden_button_host = QWidget(card)
        hidden_layout = QHBoxLayout(hidden_button_host)
        hidden_layout.setContentsMargins(0, 0, 0, 0)
        hidden_layout.setSpacing(0)
        self.add_time_phase_button = QPushButton("添加时间工步", hidden_button_host)
        self.add_voltage_phase_button = QPushButton("添加电压工步", hidden_button_host)
        self.add_rest_phase_button = QPushButton("添加静置工步", hidden_button_host)
        for button in (self.add_time_phase_button, self.add_voltage_phase_button, self.add_rest_phase_button):
            button.hide()
            hidden_layout.addWidget(button)
        card.content_layout.addWidget(hidden_button_host)
        hidden_button_host.hide()

        self.phase_container = QWidget(card)
        self.phase_layout = QVBoxLayout(self.phase_container)
        self.phase_layout.setContentsMargins(0, 0, 0, 0)
        self.phase_layout.setSpacing(10)
        card.content_layout.addWidget(self.phase_container)
        return card

    def _build_pulse_card(self) -> Card:
        card = Card("Pulse", self)
        self.pulse_form = QFormLayout()
        self.pulse_form.setContentsMargins(0, 0, 0, 0)
        self.pulse_form.setHorizontalSpacing(14)
        self.pulse_form.setVerticalSpacing(10)
        self.pulse_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.pulse_relaxation_mode_combo = NoWheelComboBox(card)
        self.pulse_relaxation_mode_combo.addItem("静置", RelaxationUiMode.REST.value)
        self.pulse_relaxation_mode_combo.addItem("恒流", RelaxationUiMode.CONSTANT_CURRENT.value)
        self.pulse_relaxation_time_edit = self._line_edit("恢复时长 / s")
        self.pulse_relaxation_current_mode_combo = NoWheelComboBox(card)
        self.pulse_relaxation_current_mode_combo.addItem("倍率", CurrentInputUiMode.RATE.value)
        self.pulse_relaxation_current_mode_combo.addItem("绝对电流", CurrentInputUiMode.ABSOLUTE.value)
        self.pulse_relaxation_rate_edit = self._line_edit("恢复倍率 / C")
        self.pulse_relaxation_current_edit = self._line_edit("恢复电流 / A")

        self.pulse_current_mode_combo = NoWheelComboBox(card)
        self.pulse_current_mode_combo.addItem("倍率", CurrentInputUiMode.RATE.value)
        self.pulse_current_mode_combo.addItem("绝对电流", CurrentInputUiMode.ABSOLUTE.value)
        self.pulse_rate_edit = self._line_edit("脉冲倍率 / C")
        self.pulse_current_edit = self._line_edit("脉冲电流 / A")
        self.pulse_duration_edit = self._line_edit("脉冲时长 / s")
        self.pulse_count_edit = self._line_edit("脉冲次数")
        self.pulse_sample_interval_edit = self._preset_combo(["0.001", "0.002", "0.005", "0.01", "0.1", "1"])
        self.pulse_upper_voltage_edit = self._line_edit("电压上限 / V")
        self.pulse_lower_voltage_edit = self._line_edit("电压下限 / V")
        self.pulse_pre_wait_edit = self._line_edit("阶段前等待 / s")

        self.pulse_form.addRow("恢复模式", self.pulse_relaxation_mode_combo)
        self.pulse_form.addRow("恢复时长 / s", self.pulse_relaxation_time_edit)
        self.pulse_form.addRow("恢复电流模式", self.pulse_relaxation_current_mode_combo)
        self.pulse_form.addRow("恢复倍率 / C", self.pulse_relaxation_rate_edit)
        self.pulse_form.addRow("恢复电流 / A", self.pulse_relaxation_current_edit)
        self.pulse_form.addRow("脉冲电流模式", self.pulse_current_mode_combo)
        self.pulse_form.addRow("脉冲倍率 / C", self.pulse_rate_edit)
        self.pulse_form.addRow("脉冲电流 / A", self.pulse_current_edit)
        self.pulse_form.addRow("脉冲时长 / s", self.pulse_duration_edit)
        self.pulse_form.addRow("脉冲次数", self.pulse_count_edit)
        self.pulse_form.addRow("采样间隔 / s", self.pulse_sample_interval_edit)
        self.pulse_form.addRow("电压上限 / V", self.pulse_upper_voltage_edit)
        self.pulse_form.addRow("电压下限 / V", self.pulse_lower_voltage_edit)
        self.pulse_form.addRow("阶段前等待 / s", self.pulse_pre_wait_edit)
        card.content_layout.addLayout(self.pulse_form)
        return card

    def _build_impedance_card(self) -> Card:
        card = Card("Impedance", self)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.use_open_circuit_init_e_box = QCheckBox("使用开路电位作为 Init E", card)
        self.init_e_v_edit = self._line_edit("Init E / V")
        self.high_frequency_edit = self._line_edit("高频 / Hz")
        self.low_frequency_edit = self._line_edit("低频 / Hz")
        self.amplitude_edit = self._line_edit("振幅 / V")
        self.quiet_time_edit = self._line_edit("静置时间 / s")

        form.addRow("", self.use_open_circuit_init_e_box)
        form.addRow("Init E / V", self.init_e_v_edit)
        form.addRow("高频 / Hz", self.high_frequency_edit)
        form.addRow("低频 / Hz", self.low_frequency_edit)
        form.addRow("振幅 / V", self.amplitude_edit)
        form.addRow("静置时间 / s", self.quiet_time_edit)
        card.content_layout.addLayout(form)
        return card

    def _line_edit(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit(self)
        edit.setPlaceholderText(placeholder)
        return edit

    def _preset_combo(self, values: list[str]) -> PresetComboBox:
        combo = PresetComboBox(values, self)
        combo.setCurrentText(values[0] if values else "")
        return combo

    def _metric_pill(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setObjectName("metricPill")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _connect_signals(self) -> None:
        self.mode_combo.currentIndexChanged.connect(self._sync_workspace_mode)
        self.mode_combo.currentIndexChanged.connect(self.schedule_refresh)
        self.new_preset_button.clicked.connect(self.new_preset)
        self.open_preset_button.clicked.connect(self.open_preset)
        self.save_preset_button.clicked.connect(self.save_preset)
        self.save_as_preset_button.clicked.connect(self.save_preset_as)
        self.recent_presets_combo.activated.connect(self._open_selected_recent_preset)
        self.export_dir_browse_button.clicked.connect(self._browse_export_directory)

        for edit in (
            self.scheme_name_edit,
            self.file_prefix_edit,
            self.export_dir_edit,
            self.active_material_edit,
            self.theoretical_capacity_edit,
            self.init_e_v_edit,
            self.high_frequency_edit,
            self.low_frequency_edit,
            self.amplitude_edit,
            self.quiet_time_edit,
            self.pulse_relaxation_time_edit,
            self.pulse_relaxation_rate_edit,
            self.pulse_relaxation_current_edit,
            self.pulse_rate_edit,
            self.pulse_current_edit,
            self.pulse_duration_edit,
            self.pulse_count_edit,
            self.pulse_upper_voltage_edit,
            self.pulse_lower_voltage_edit,
            self.pulse_pre_wait_edit,
        ):
            edit.textChanged.connect(self.schedule_refresh)

        for combo in (
            self.pulse_relaxation_mode_combo,
            self.pulse_relaxation_current_mode_combo,
            self.pulse_current_mode_combo,
            self.pulse_sample_interval_edit,
        ):
            if isinstance(combo, PresetComboBox):
                combo.currentIndexChanged.connect(self.schedule_refresh)
                combo.lineEdit().textChanged.connect(self.schedule_refresh)
            else:
                combo.currentIndexChanged.connect(self.schedule_refresh)

        self.use_open_circuit_init_e_box.toggled.connect(self._sync_init_e_visibility)
        self.use_open_circuit_init_e_box.toggled.connect(self.schedule_refresh)
        self.pulse_relaxation_mode_combo.currentIndexChanged.connect(self._sync_pulse_field_visibility)
        self.pulse_relaxation_current_mode_combo.currentIndexChanged.connect(self._sync_pulse_field_visibility)
        self.pulse_current_mode_combo.currentIndexChanged.connect(self._sync_pulse_field_visibility)

        self.add_workstep_button.clicked.connect(lambda: self._append_phase(PhaseUiKind.TIME_POINTS))
        self.add_time_phase_button.clicked.connect(lambda: self._append_phase(PhaseUiKind.TIME_POINTS))
        self.add_voltage_phase_button.clicked.connect(lambda: self._append_phase(PhaseUiKind.VOLTAGE_POINTS))
        self.add_rest_phase_button.clicked.connect(lambda: self._append_phase(PhaseUiKind.REST))
        self.time_template_button.clicked.connect(self._apply_time_template)
        self.voltage_template_button.clicked.connect(self._apply_voltage_template)
        self.activation_template_button.clicked.connect(self._apply_activation_template)

    def _apply_defaults(self) -> None:
        self._updating_ui = True
        try:
            defaults = GuiState()
            self.scheme_name_edit.setText(defaults.scheme_name)
            self.file_prefix_edit.setText(defaults.file_prefix)
            self.export_dir_edit.setText(defaults.export_dir)
            self.active_material_edit.setText(defaults.active_material_mg)
            self.theoretical_capacity_edit.setText(defaults.theoretical_capacity_mah_mg)
            self.use_open_circuit_init_e_box.setChecked(defaults.use_open_circuit_init_e)
            self.init_e_v_edit.setText(defaults.init_e_v)
            self.high_frequency_edit.setText(defaults.high_frequency_hz)
            self.low_frequency_edit.setText(defaults.low_frequency_hz)
            self.amplitude_edit.setText(defaults.amplitude_v)
            self.quiet_time_edit.setText(defaults.quiet_time_s)
            self.pulse_relaxation_mode_combo.setCurrentIndex(
                self.pulse_relaxation_mode_combo.findData(defaults.pulse_relaxation_mode.value)
            )
            self.pulse_relaxation_time_edit.setText(defaults.pulse_relaxation_time_s)
            self.pulse_relaxation_current_mode_combo.setCurrentIndex(
                self.pulse_relaxation_current_mode_combo.findData(defaults.pulse_relaxation_current_mode.value)
            )
            self.pulse_relaxation_rate_edit.setText(defaults.pulse_relaxation_rate_c)
            self.pulse_relaxation_current_edit.setText(defaults.pulse_relaxation_current_a)
            self.pulse_current_mode_combo.setCurrentIndex(self.pulse_current_mode_combo.findData(defaults.pulse_current_mode.value))
            self.pulse_rate_edit.setText(defaults.pulse_current_rate_c)
            self.pulse_current_edit.setText(defaults.pulse_current_a)
            self.pulse_duration_edit.setText(defaults.pulse_duration_s)
            self.pulse_count_edit.setText(defaults.pulse_count)
            self.pulse_sample_interval_edit.setEditText(defaults.pulse_sample_interval_s)
            self.pulse_upper_voltage_edit.setText(defaults.pulse_upper_voltage_v)
            self.pulse_lower_voltage_edit.setText(defaults.pulse_lower_voltage_v)
            self.pulse_pre_wait_edit.setText(defaults.pulse_pre_wait_s)
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(defaults.workspace_mode.value))
            self._rebuild_phase_rows(defaults.phases)
        finally:
            self._updating_ui = False
        self._sync_workspace_mode()
        self._sync_pulse_field_visibility()
        self._sync_init_e_visibility()
        self._refresh_workstep_metrics()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f4f7fb, stop:1 #eef3f9);
                color: #0f172a;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
                font-size: 10pt;
            }
            QWidget {
                color: #0f172a;
                font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
            }
            QFrame[card="true"] {
                background: rgba(255, 255, 255, 0.86);
                border: 1px solid rgba(182, 197, 214, 0.72);
                border-radius: 20px;
            }
            QFrame[hero="true"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(16, 71, 164, 0.97), stop:1 rgba(84, 143, 232, 0.92));
                border: 0;
                border-radius: 18px;
            }
            QLabel#cardTitle {
                font-size: 15pt;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#heroKicker {
                color: rgba(255, 255, 255, 0.82);
                font-size: 9pt;
                font-weight: 600;
                letter-spacing: 0.4px;
            }
            QLabel#heroTitle {
                color: white;
                font-size: 21pt;
                font-weight: 750;
            }
            QLabel#heroBody {
                color: rgba(255, 255, 255, 0.88);
                font-size: 10pt;
            }
            QLabel#metaLabel, QLabel#mutedLabel, QLabel#phaseHint, QLabel#fieldLabel {
                color: #526277;
            }
            QLabel#metricText, QLabel#accentValue {
                color: #1357d6;
                font-weight: 700;
            }
            QLabel#inlineValue {
                color: #334155;
                font-weight: 600;
            }
            QLabel#metricPill, QLabel#pointPill {
                background: rgba(19, 87, 214, 0.10);
                color: #1357d6;
                border: 1px solid rgba(19, 87, 214, 0.18);
                border-radius: 999px;
                padding: 6px 12px;
                font-weight: 700;
            }
            QLabel#stepBadge {
                background: #1357d6;
                color: white;
                border-radius: 12px;
                padding: 8px 12px;
                font-weight: 800;
            }
            QFrame[workstepRow="true"] {
                background: rgba(252, 253, 255, 0.95);
                border: 1px solid rgba(193, 205, 220, 0.84);
                border-radius: 18px;
            }
            QLineEdit, QComboBox, QPlainTextEdit {
                background: white;
                border: 1px solid #c9d3e1;
                border-radius: 12px;
                padding: 8px 12px;
                selection-background-color: #1357d6;
            }
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
                border: 1px solid #1357d6;
            }
            QPushButton {
                border-radius: 12px;
                border: 1px solid #c3cfde;
                background: rgba(255, 255, 255, 0.92);
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #f6f9ff;
                border-color: #a7b9d1;
            }
            QPushButton#primaryButton {
                background: #1357d6;
                border: 1px solid #1357d6;
                color: white;
                padding: 9px 18px;
                font-weight: 700;
            }
            QPushButton#primaryButton:hover {
                background: #1049b5;
                border-color: #1049b5;
            }
            QPushButton#ghostButton, QPushButton#rowGhostButton {
                background: rgba(255, 255, 255, 0.88);
            }
            QPushButton#secondaryButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1357d6, stop:1 #2f7cff);
                border: 1px solid #1357d6;
                color: white;
                padding: 9px 16px;
                font-weight: 700;
            }
            QPushButton#secondaryButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1049b5, stop:1 #2467db);
                border-color: #1049b5;
            }
            QPushButton#secondaryButton:pressed {
                background: #0e3f9a;
            }
            QPushButton#secondaryButton[copied="true"] {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f9f6e, stop:1 #25c286);
                border: 1px solid #0f9f6e;
            }
            QToolButton#inlineButton {
                background: rgba(19, 87, 214, 0.08);
                border: 1px solid rgba(19, 87, 214, 0.16);
                border-radius: 12px;
                color: #1357d6;
                padding: 8px 12px;
                font-weight: 700;
            }
            QLabel#summaryPanel, QPlainTextEdit#summaryPanel {
                background: rgba(246, 249, 255, 0.94);
                border: 1px solid rgba(195, 207, 222, 0.82);
                border-radius: 16px;
                padding: 14px;
                color: #1e293b;
            }
            QLabel#panelLabel {
                font-size: 10pt;
                font-weight: 700;
                color: #0f172a;
            }
            QListWidget {
                background: rgba(255, 255, 255, 0.95);
                border: 1px solid rgba(195, 207, 222, 0.82);
                border-radius: 16px;
                padding: 6px;
            }
            """
        )

    def _make_default_phase(self, kind: PhaseUiKind, index: int) -> GuiPhaseState:
        if kind is PhaseUiKind.VOLTAGE_POINTS:
            return GuiPhaseState(label=f"工步 {index}", phase_kind=PhaseUiKind.VOLTAGE_POINTS)
        if kind is PhaseUiKind.REST:
            return GuiPhaseState(label=f"工步 {index}", phase_kind=PhaseUiKind.REST)
        return GuiPhaseState(label=f"工步 {index}", phase_kind=PhaseUiKind.TIME_POINTS)

    def _rebuild_phase_rows(self, phase_states: list[GuiPhaseState]) -> None:
        while self.phase_layout.count():
            item = self.phase_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.phase_editors.clear()
        seed_states = phase_states or [GuiPhaseState()]
        for index, state in enumerate(seed_states, start=1):
            row = WorkstepEditorRow(
                index=index,
                state=state,
                on_change=self.schedule_refresh,
                on_move_up=self._move_phase_up,
                on_move_down=self._move_phase_down,
                on_delete=self._delete_phase,
                parent=self.phase_container,
            )
            self.phase_layout.addWidget(row)
            self.phase_editors.append(row)
        self._sync_phase_order_state()

    def _sync_phase_order_state(self) -> None:
        total = len(self.phase_editors)
        for index, row in enumerate(self.phase_editors, start=1):
            row.set_order_state(index, total)
        self._refresh_workstep_metrics()

    def _append_phase(self, kind: PhaseUiKind) -> None:
        states = [row.collect_state() for row in self.phase_editors]
        states.append(self._make_default_phase(kind, len(states) + 1))
        self._rebuild_phase_rows(states)
        self.schedule_refresh()

    def _move_phase_up(self, row: WorkstepEditorRow) -> None:
        index = self.phase_editors.index(row)
        if index <= 0:
            return
        states = [editor.collect_state() for editor in self.phase_editors]
        states[index - 1], states[index] = states[index], states[index - 1]
        self._rebuild_phase_rows(states)
        self.schedule_refresh()

    def _move_phase_down(self, row: WorkstepEditorRow) -> None:
        index = self.phase_editors.index(row)
        if index >= len(self.phase_editors) - 1:
            return
        states = [editor.collect_state() for editor in self.phase_editors]
        states[index + 1], states[index] = states[index], states[index + 1]
        self._rebuild_phase_rows(states)
        self.schedule_refresh()

    def _delete_phase(self, row: WorkstepEditorRow) -> None:
        if len(self.phase_editors) <= 1:
            return
        states = [editor.collect_state() for editor in self.phase_editors if editor is not row]
        self._rebuild_phase_rows(states)
        self.schedule_refresh()

    def _apply_time_template(self) -> None:
        self._rebuild_phase_rows([GuiPhaseState(label="工步 1", phase_kind=PhaseUiKind.TIME_POINTS)])
        self.schedule_refresh()

    def _apply_voltage_template(self) -> None:
        self._rebuild_phase_rows([GuiPhaseState(label="工步 1", phase_kind=PhaseUiKind.VOLTAGE_POINTS)])
        self.schedule_refresh()

    def _apply_activation_template(self) -> None:
        states = [
            GuiPhaseState(label="工步 1", phase_kind=PhaseUiKind.TIME_POINTS, direction="charge"),
            GuiPhaseState(label="工步 2", phase_kind=PhaseUiKind.REST, rest_duration_s="300"),
            GuiPhaseState(label="工步 3", phase_kind=PhaseUiKind.TIME_POINTS, direction="discharge"),
        ]
        self._rebuild_phase_rows(states)
        self.schedule_refresh()

    def _collect_state(self) -> GuiState:
        return GuiState.model_validate(
            {
                "workspace_mode": self.mode_combo.currentData(),
                "scheme_name": self.scheme_name_edit.text() or "CHI 原位阻抗",
                "file_prefix": self.file_prefix_edit.text() or "CHI",
                "export_dir": self.export_dir_edit.text(),
                "active_material_mg": self.active_material_edit.text() or "1",
                "theoretical_capacity_mah_mg": self.theoretical_capacity_edit.text() or "865",
                "phases": [row.collect_state() for row in self.phase_editors] or [GuiPhaseState()],
                "use_open_circuit_init_e": self.use_open_circuit_init_e_box.isChecked(),
                "init_e_v": self.init_e_v_edit.text() or "3.2",
                "high_frequency_hz": self.high_frequency_edit.text() or "100000",
                "low_frequency_hz": self.low_frequency_edit.text() or "0.01",
                "amplitude_v": self.amplitude_edit.text() or "0.005",
                "quiet_time_s": self.quiet_time_edit.text() or "2",
                "pulse_relaxation_mode": self.pulse_relaxation_mode_combo.currentData(),
                "pulse_relaxation_time_s": self.pulse_relaxation_time_edit.text() or "60",
                "pulse_relaxation_current_mode": self.pulse_relaxation_current_mode_combo.currentData(),
                "pulse_relaxation_rate_c": self.pulse_relaxation_rate_edit.text() or "0.02",
                "pulse_relaxation_current_a": self.pulse_relaxation_current_edit.text() or "0.00002",
                "pulse_current_mode": self.pulse_current_mode_combo.currentData(),
                "pulse_current_rate_c": self.pulse_rate_edit.text() or "1",
                "pulse_current_a": self.pulse_current_edit.text() or "0.001",
                "pulse_duration_s": self.pulse_duration_edit.text() or "5",
                "pulse_count": self.pulse_count_edit.text() or "1",
                "pulse_sample_interval_s": self.pulse_sample_interval_edit.currentText() or "0.001",
                "pulse_upper_voltage_v": self.pulse_upper_voltage_edit.text() or "4",
                "pulse_lower_voltage_v": self.pulse_lower_voltage_edit.text() or "-1",
                "pulse_pre_wait_s": self.pulse_pre_wait_edit.text() or "0",
            }
        )

    def _apply_state(self, state: GuiState) -> None:
        self._updating_ui = True
        try:
            self.mode_combo.setCurrentIndex(self.mode_combo.findData(state.workspace_mode.value))
            self.scheme_name_edit.setText(state.scheme_name)
            self.file_prefix_edit.setText(state.file_prefix)
            self.export_dir_edit.setText(state.export_dir)
            self.active_material_edit.setText(state.active_material_mg)
            self.theoretical_capacity_edit.setText(state.theoretical_capacity_mah_mg)
            self._rebuild_phase_rows(state.phases)
            self.use_open_circuit_init_e_box.setChecked(state.use_open_circuit_init_e)
            self.init_e_v_edit.setText(state.init_e_v)
            self.high_frequency_edit.setText(state.high_frequency_hz)
            self.low_frequency_edit.setText(state.low_frequency_hz)
            self.amplitude_edit.setText(state.amplitude_v)
            self.quiet_time_edit.setText(state.quiet_time_s)
            self.pulse_relaxation_mode_combo.setCurrentIndex(
                self.pulse_relaxation_mode_combo.findData(state.pulse_relaxation_mode.value)
            )
            self.pulse_relaxation_time_edit.setText(state.pulse_relaxation_time_s)
            self.pulse_relaxation_current_mode_combo.setCurrentIndex(
                self.pulse_relaxation_current_mode_combo.findData(state.pulse_relaxation_current_mode.value)
            )
            self.pulse_relaxation_rate_edit.setText(state.pulse_relaxation_rate_c)
            self.pulse_relaxation_current_edit.setText(state.pulse_relaxation_current_a)
            self.pulse_current_mode_combo.setCurrentIndex(self.pulse_current_mode_combo.findData(state.pulse_current_mode.value))
            self.pulse_rate_edit.setText(state.pulse_current_rate_c)
            self.pulse_current_edit.setText(state.pulse_current_a)
            self.pulse_duration_edit.setText(state.pulse_duration_s)
            self.pulse_count_edit.setText(state.pulse_count)
            self.pulse_sample_interval_edit.setEditText(state.pulse_sample_interval_s)
            self.pulse_upper_voltage_edit.setText(state.pulse_upper_voltage_v)
            self.pulse_lower_voltage_edit.setText(state.pulse_lower_voltage_v)
            self.pulse_pre_wait_edit.setText(state.pulse_pre_wait_s)
        finally:
            self._updating_ui = False
        self._sync_workspace_mode()
        self._sync_init_e_visibility()
        self._sync_pulse_field_visibility()
        self.refresh_preview()

    def _sync_workspace_mode(self) -> None:
        is_sequence = self.mode_combo.currentData() == WorkspaceMode.SEQUENCE.value
        self.workstep_card.setVisible(is_sequence)
        self.pulse_card.setVisible(not is_sequence)
        self.workspace_mode_label.setText("Sequence Workspace" if is_sequence else "Pulse Workspace")
        self.workspace_headline.setText("交替工步在同一条工作流里完成" if is_sequence else "脉冲段与恢复段在同一张表里校准")
        self.workspace_copy.setText(
            "统一从工步表格编辑，模板只负责快速起手。"
            if is_sequence
            else "Pulse 保留独立页面，恢复段与脉冲段按模式联动显示。"
        )
        self._refresh_workstep_metrics()

    def _sync_init_e_visibility(self) -> None:
        visible = not self.use_open_circuit_init_e_box.isChecked()
        self.init_e_v_edit.setVisible(visible)
        form = self.impedance_card.content_layout.itemAt(0).layout()
        if isinstance(form, QFormLayout):
            label = form.labelForField(self.init_e_v_edit)
            if label is not None:
                label.setVisible(visible)

    def _sync_pulse_field_visibility(self) -> None:
        relaxation_mode = self.pulse_relaxation_mode_combo.currentData()
        relaxation_mode_is_cc = relaxation_mode == RelaxationUiMode.CONSTANT_CURRENT.value
        pulse_mode_is_absolute = self.pulse_current_mode_combo.currentData() == CurrentInputUiMode.ABSOLUTE.value
        relaxation_mode_is_absolute = self.pulse_relaxation_current_mode_combo.currentData() == CurrentInputUiMode.ABSOLUTE.value

        self._set_form_row_visible(self.pulse_form, self.pulse_relaxation_current_mode_combo, relaxation_mode_is_cc)
        self._set_form_row_visible(
            self.pulse_form,
            self.pulse_relaxation_rate_edit,
            relaxation_mode_is_cc and not relaxation_mode_is_absolute,
        )
        self._set_form_row_visible(
            self.pulse_form,
            self.pulse_relaxation_current_edit,
            relaxation_mode_is_cc and relaxation_mode_is_absolute,
        )
        self._set_form_row_visible(self.pulse_form, self.pulse_rate_edit, not pulse_mode_is_absolute)
        self._set_form_row_visible(self.pulse_form, self.pulse_current_edit, pulse_mode_is_absolute)

    def _set_form_row_visible(self, form: QFormLayout, widget: QWidget, visible: bool) -> None:
        label = form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)
        widget.setVisible(visible)

    def _refresh_workstep_metrics(self, bundle: ScriptBundle | None = None) -> None:
        if self.mode_combo.currentData() != WorkspaceMode.SEQUENCE.value:
            self.workstep_count_pill.setText("Pulse")
            self.total_points_pill.setText("0 点")
            self.total_eis_pill.setText("0 EIS")
            return
        if isinstance(bundle, SequenceScriptBundle):
            workstep_count = len(bundle.phase_plans)
            total_points = bundle.total_point_count
            total_eis = bundle.total_eis_count
        else:
            workstep_count = len(self.phase_editors)
            total_points = 0
            total_eis = 0
            for row in self.phase_editors:
                digits = [int(token) for token in re.findall(r"\d+", row.point_count_label.text())[:2]]
                if digits:
                    total_points += digits[0]
                if len(digits) > 1:
                    total_eis += digits[1]
        self.workstep_count_pill.setText(f"{workstep_count} 个工步")
        self.total_points_pill.setText(f"{total_points} 点")
        self.total_eis_pill.setText(f"{total_eis} EIS")

    def schedule_refresh(self, *_: object) -> None:
        if self._updating_ui:
            return
        self._refresh_timer.start()

    def refresh_preview(self, *_: object) -> None:
        if self._updating_ui:
            return
        try:
            state = self._collect_state()
            bundle = self._backend.preview(state)
            self._last_bundle = bundle
            self.issue_list.set_issues(bundle.issues)
            self.output_panel.set_scripts(
                bundle.commented_script,
                bundle.minimal_script,
                "\n".join(bundle.summary_lines),
                bundle.can_generate,
            )
            self._update_current_preview(state)
            self._refresh_workstep_metrics(bundle)
            self._update_status_bar(bundle)
        except Exception as exc:  # pragma: no cover - protective UI path
            issue = ValidationIssue(severity=Severity.ERROR, code="ui.refresh", message=str(exc))
            self._last_bundle = None
            self.issue_list.set_issues([issue])
            self.output_panel.set_scripts("", "", str(exc), False)
            self._refresh_workstep_metrics()
            self.statusBar().showMessage(f"预览失败: {exc}")

    def _update_current_preview(self, state: GuiState) -> None:
        try:
            one_c_current_a, operating_current_a, operating_rate_c = self._backend.resolve_current_preview(state)
        except Exception:
            self.current_operating_value.setText("-")
            self.current_preview_label.setText("-")
            return
        summary = f"{operating_current_a:.9f} A  |  {operating_rate_c:g} C  |  1C = {one_c_current_a:.9f} A"
        self.current_operating_value.setText(summary)
        self.current_preview_label.setText(summary)

    def _update_status_bar(self, bundle: ScriptBundle) -> None:
        error_count = sum(1 for issue in bundle.issues if issue.severity is Severity.ERROR)
        warning_count = sum(1 for issue in bundle.issues if issue.severity is Severity.WARNING)
        self.statusBar().showMessage(f"错误 {error_count}  |  警告 {warning_count}")

    def _browse_export_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择导出目录", self.export_dir_edit.text() or str(Path.cwd()))
        if directory:
            self.export_dir_edit.setText(directory)

    def new_preset(self) -> None:
        self._current_preset_path = None
        self._apply_state(GuiState())

    def open_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开预设",
            str(self._current_preset_path.parent if self._current_preset_path else Path.cwd()),
            "CHI Preset (*.chi-preset)",
        )
        if path:
            self.load_preset_from_path(path)

    def save_preset(self) -> None:
        if self._current_preset_path is None:
            self.save_preset_as()
            return
        self.save_preset_to_path(self._current_preset_path)

    def save_preset_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存预设",
            str(self._current_preset_path or (Path.cwd() / "workflow.chi-preset")),
            "CHI Preset (*.chi-preset)",
        )
        if path:
            self.save_preset_to_path(path)

    def save_preset_to_path(self, path: str | Path) -> Path:
        saved_path = self._preset_service.save_preset(path, self._collect_state())
        self._current_preset_path = saved_path
        self._update_recent_presets()
        return saved_path

    def load_preset_from_path(self, path: str | Path) -> None:
        loaded_state = self._preset_service.load_preset(path)
        self._current_preset_path = self._preset_service.normalize_preset_path(path)
        self._update_recent_presets()
        self._apply_state(loaded_state)

    def _save_preset_path(self, path: str | Path) -> Path:
        return self.save_preset_to_path(path)

    def _load_preset_path(self, path: str | Path) -> None:
        self.load_preset_from_path(path)

    def _update_recent_presets(self) -> None:
        current_path = self.recent_presets_combo.currentData()
        self.recent_presets_combo.blockSignals(True)
        self.recent_presets_combo.clear()
        self.recent_presets_combo.addItem("最近预设", "")
        for path in self._preset_service.load_recent_files():
            self.recent_presets_combo.addItem(path.name, str(path))
        if current_path:
            index = self.recent_presets_combo.findData(current_path)
            if index >= 0:
                self.recent_presets_combo.setCurrentIndex(index)
        else:
            self.recent_presets_combo.setCurrentIndex(0)
        self.recent_presets_combo.blockSignals(False)

    def _open_selected_recent_preset(self) -> None:
        path = self.recent_presets_combo.currentData()
        if path:
            self.load_preset_from_path(path)


__all__ = ["MainWindow"]
