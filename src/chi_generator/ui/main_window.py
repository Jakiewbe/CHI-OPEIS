"""Main application window for the CHI in-situ EIS generator."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QSizePolicy, QSplitter, QStatusBar, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF, LineEdit, MSFluentWindow, PrimaryPushButton, PushButton, ScrollArea, Theme, setTheme

from chi_generator.domain.models import ImpedanceMeasurementMode, ProcessDirection, SamplingMode, ScriptBundle, ScriptKind, SequenceScriptBundle, Severity, ValidationIssue
from chi_generator.ui.adapters import GuiBackend
from chi_generator.ui.models import CurrentBasisUiMode, CurrentInputUiMode, GuiLoopState, GuiPhaseState, GuiState, PhaseUiKind, RelaxationUiMode, WorkflowItemState, WorkspaceMode, expand_workflow_items
from chi_generator.ui.preview_chart import ScriptPreviewChart
from chi_generator.ui.presets import PresetFileService
from chi_generator.ui.planning import parse_float_list
from chi_generator.ui.widgets import Card, GuidedManualPointDialog, IssueListWidget, LoopBlockWidget, NoWheelComboBox, PresetComboBox, ScriptOutputPanel, WorkstepEditorRow


class MainWindow(MSFluentWindow):
    """Fluent desktop UI for sequence and pulse script generation."""

    def __init__(self, service: object | None = None, parent: QWidget | None = None, preset_service: PresetFileService | None = None) -> None:
        super().__init__(parent)
        setTheme(Theme.DARK)
        self.setMicaEffectEnabled(False)
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
        self.workflow_widgets: list[WorkstepEditorRow | LoopBlockWidget] = []
        self._build_ui()
        self._connect_signals()
        self._apply_defaults()
        self._update_recent_presets()
        self.refresh_preview()

    def _build_ui(self) -> None:
        self.setWindowTitle("CHI 原位EIS脚本生成器")
        self.resize(1520, 940)
        self.setMinimumSize(1280, 840)
        self.workspace_page = QWidget(self)
        self.workspace_page.setObjectName("workspacePage")
        page_layout = QVBoxLayout(self.workspace_page)
        page_layout.setContentsMargins(14, 14, 14, 10)
        page_layout.setSpacing(10)
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal, self.workspace_page)
        self.workspace_splitter.setChildrenCollapsible(False)
        self.left_panel = self._build_left_panel()
        self.right_panel = self._build_right_panel()
        self.right_panel.setMaximumWidth(560)
        self.workspace_splitter.addWidget(self.left_panel)
        self.workspace_splitter.addWidget(self.right_panel)
        self.workspace_splitter.setStretchFactor(0, 1)
        self.workspace_splitter.setStretchFactor(1, 0)
        self.workspace_splitter.setSizes([1080, 420])
        self._status_bar = QStatusBar(self.workspace_page)
        self._status_bar.setSizeGripEnabled(False)
        page_layout.addWidget(self.workspace_splitter, 1)
        page_layout.addWidget(self._status_bar)
        self.addSubInterface(self.workspace_page, FIF.APPLICATION, "工作区")
        self.navigationInterface.setCurrentItem(self.workspace_page.objectName())
        self._apply_styles()

    def statusBar(self) -> QStatusBar:
        return self._status_bar

    def _build_left_panel(self) -> QWidget:
        root = QWidget(self)
        root.setObjectName("leftPanel")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = ScrollArea(root)
        scroll.setObjectName("leftScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(scroll)
        body.setObjectName("leftScrollBody")
        self.left_layout = QVBoxLayout(body)
        self.left_layout.setContentsMargins(10, 10, 10, 10)
        self.left_layout.setSpacing(14)
        self.workspace_card = self._build_workspace_card()
        self.project_card = self._build_project_card()
        self.battery_card = self._build_battery_card()
        self.workstep_card = self._build_workstep_card()
        self.pulse_card = self._build_pulse_card()
        self.impedance_card = self._build_impedance_card()
        for card in (self.workspace_card, self.project_card, self.battery_card, self.workstep_card, self.pulse_card, self.impedance_card):
            self.left_layout.addWidget(card)
        self.left_layout.addStretch(1)
        scroll.setWidget(body)
        layout.addWidget(scroll)
        return root

    def _build_right_panel(self) -> QWidget:
        scroll = ScrollArea(self)
        scroll.setObjectName("rightScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget(scroll)
        panel.setObjectName("rightPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        self.status_card = Card("总览", panel, "当前方案、1C 基准与生成状态。")
        self.workspace_mode_label = QLabel("序列模式", self.status_card)
        self.workspace_headline = QLabel("工步列表在左，脚本与风险预览在右。", self.status_card)
        self.workspace_copy = QLabel("生成前会突出显示高风险设置、SoC 风险和可能丢失的点位。", self.status_card)
        self.current_preview_label = QLabel("-", self.status_card)
        for widget in (self.workspace_mode_label, self.workspace_headline, self.workspace_copy, self.current_preview_label):
            widget.setWordWrap(True)
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            self.status_card.content_layout.addWidget(widget)
        self.status_card.setMinimumHeight(220)
        self.status_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.status_card)
        self.issue_card = Card("警告与错误", panel, "生成前必须先确认的风险提示。")
        self.issue_list = IssueListWidget(self.issue_card)
        self.issue_card.content_layout.addWidget(self.issue_list)
        self.issue_card.setMaximumHeight(170)
        layout.addWidget(self.issue_card, 1)
        self.planning_card = Card("采样看板", panel, "查看 EIS 中断与 SoC 预测。")
        self.preview_chart = ScriptPreviewChart(self.planning_card)
        self.planning_card.content_layout.addWidget(self.preview_chart)
        self.planning_card.setMinimumHeight(300)
        layout.addWidget(self.planning_card, 1)
        self.preview_card = Card("脚本预览", panel, "可直接复制到 CHI Macro Command。")
        self.output_panel = ScriptOutputPanel(self.preview_card)
        self.preview_card.content_layout.addWidget(self.output_panel)
        self.preview_card.setMinimumHeight(420)
        layout.addWidget(self.preview_card, 3)
        layout.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    def _build_workspace_card(self) -> Card:
        card = Card("工作区", self, "选择脚本模式，管理本地预设。")
        top_row = QHBoxLayout()
        branding = QVBoxLayout()
        branding.addWidget(QLabel("CHI 原位阻抗", card))
        copy = QLabel("聚焦工步序列编辑与脚本预览。", card)
        copy.setWordWrap(True)
        branding.addWidget(copy)
        mode_box = QVBoxLayout()
        mode_box.addWidget(QLabel("模式", card))
        self.mode_combo = NoWheelComboBox(card)
        self.mode_combo.addItem("序列", WorkspaceMode.SEQUENCE.value)
        self.mode_combo.addItem("脉冲", WorkspaceMode.PULSE.value)
        self.mode_combo.setMinimumWidth(180)
        self._scenario = self.mode_combo
        mode_box.addWidget(self.mode_combo)
        top_row.addLayout(branding, 1)
        top_row.addLayout(mode_box)
        card.content_layout.addLayout(top_row)
        preset_row = QHBoxLayout()
        self.new_preset_button = self._button("新建", card)
        self.open_preset_button = self._button("打开", card)
        self.save_preset_button = self._button("保存", card)
        self.save_as_preset_button = self._button("另存为", card)
        self.recent_presets_combo = NoWheelComboBox(card)
        self.recent_presets_combo.setMinimumWidth(220)
        self.recent_presets_combo.addItem("最近预设", "")
        for button in (self.new_preset_button, self.open_preset_button, self.save_preset_button, self.save_as_preset_button):
            preset_row.addWidget(button)
        preset_row.addStretch(1)
        preset_row.addWidget(self.recent_presets_combo)
        card.content_layout.addLayout(preset_row)
        return card

    def _build_project_card(self) -> Card:
        card = Card("项目", self, "文件名前缀与导出位置会写入最终宏命令。")
        form = QFormLayout()
        self.scheme_name_edit = self._line_edit("方案名称")
        self.file_prefix_edit = self._line_edit("文件前缀")
        self.export_dir_edit = self._line_edit("导出目录")
        export_row = QHBoxLayout()
        export_row.addWidget(self.export_dir_edit, 1)
        self.export_dir_browse_button = self._button("浏览", card)
        export_row.addWidget(self.export_dir_browse_button)
        wrap = QWidget(card)
        wrap.setLayout(export_row)
        form.addRow("方案名称", self.scheme_name_edit)
        form.addRow("文件前缀", self.file_prefix_edit)
        form.addRow("导出目录", wrap)
        card.content_layout.addLayout(form)
        return card

    def _build_battery_card(self) -> Card:
        card = Card("电池与电流", self, "设置 1C 基准，后续倍率会统一换算为安培。")
        self.battery_form = QFormLayout()
        self.active_material_edit = self._line_edit("活性物质量 / mg")
        self.theoretical_capacity_edit = self._line_edit("理论比容量 / mAh g-1")
        self.current_basis_mode_combo = NoWheelComboBox(card)
        self.current_basis_mode_combo.addItem("按材料理论容量", CurrentBasisUiMode.MATERIAL.value)
        self.current_basis_mode_combo.addItem("按已知倍率电流", CurrentBasisUiMode.REFERENCE.value)
        self.reference_rate_edit = self._line_edit("已知倍率 / C")
        self.reference_current_edit = self._line_edit("对应电流 / A")
        self.current_basis_value = QLabel("半电池通常直接按材料参数换算 1C。", card)
        self.current_operating_value = QLabel("-", card)
        self.battery_form.addRow("活性物质量 / mg", self.active_material_edit)
        self.battery_form.addRow("理论比容量 / mAh g-1", self.theoretical_capacity_edit)
        self.battery_form.addRow("1C 换算方式", self.current_basis_mode_combo)
        self.battery_form.addRow("已知倍率 / C", self.reference_rate_edit)
        self.battery_form.addRow("对应电流 / A", self.reference_current_edit)
        self.battery_form.addRow("1C 基准", self.current_basis_value)
        self.battery_form.addRow("当前预览", self.current_operating_value)
        card.content_layout.addLayout(self.battery_form)
        return card

    def _build_workstep_card(self) -> Card:
        card = Card("工步列表", self, "从上到下执行；每个点后可独立插入 EIS。")
        header = QHBoxLayout()
        self.workstep_count_pill = self._metric_pill("1 个工步")
        self.total_points_pill = self._metric_pill("0 点")
        self.total_eis_pill = self._metric_pill("0 次 EIS")
        header.addStretch(1)
        header.addWidget(self.workstep_count_pill)
        header.addWidget(self.total_points_pill)
        header.addWidget(self.total_eis_pill)
        card.content_layout.addLayout(header)
        toolbar = QHBoxLayout()
        self.add_workstep_button = self._button("新增时间工步", card, primary=True)
        self.add_voltage_phase_button = self._button("新增电压工步", card)
        self.add_rest_phase_button = self._button("新增静置工步", card)
        self.create_loop_button = self._button("创建循环块", card)
        toolbar.addWidget(self.add_workstep_button)
        toolbar.addWidget(self.add_voltage_phase_button)
        toolbar.addWidget(self.add_rest_phase_button)
        toolbar.addWidget(self.create_loop_button)
        toolbar.addStretch(1)
        card.content_layout.addLayout(toolbar)
        intro = QLabel("“点前等待”只作用于受控工步；“静置工步”表示真正独立的静置阶段。", card)
        intro.setWordWrap(True)
        card.content_layout.addWidget(intro)
        self.phase_container = QWidget(card)
        self.phase_layout = QVBoxLayout(self.phase_container)
        self.phase_layout.setContentsMargins(0, 0, 0, 0)
        self.phase_layout.setSpacing(10)
        card.content_layout.addWidget(self.phase_container)
        return card

    def _build_pulse_card(self) -> Card:
        card = Card("脉冲参数", self, "按固定顺序渲染弛豫、脉冲、前后 EIS 与可选尾段。")
        self.pulse_form = QFormLayout()
        self.pulse_relaxation_mode_combo = NoWheelComboBox(card)
        self.pulse_relaxation_mode_combo.addItem("静置", RelaxationUiMode.REST.value)
        self.pulse_relaxation_mode_combo.addItem("恒流", RelaxationUiMode.CONSTANT_CURRENT.value)
        self.pulse_relaxation_time_edit = self._line_edit("弛豫时间 / s")
        self.pulse_relaxation_current_mode_combo = NoWheelComboBox(card)
        self.pulse_relaxation_current_mode_combo.addItem("倍率", CurrentInputUiMode.RATE.value)
        self.pulse_relaxation_current_mode_combo.addItem("绝对电流", CurrentInputUiMode.ABSOLUTE.value)
        self.pulse_relaxation_rate_edit = self._line_edit("弛豫倍率 / C")
        self.pulse_relaxation_current_edit = self._line_edit("弛豫电流 / A")
        self.pulse_current_mode_combo = NoWheelComboBox(card)
        self.pulse_current_mode_combo.addItem("倍率", CurrentInputUiMode.RATE.value)
        self.pulse_current_mode_combo.addItem("绝对电流", CurrentInputUiMode.ABSOLUTE.value)
        self.pulse_rate_edit = self._line_edit("脉冲倍率 / C")
        self.pulse_current_edit = self._line_edit("脉冲电流 / A")
        self.pulse_duration_edit = self._line_edit("脉冲时长 / s")
        self.pulse_count_edit = self._line_edit("脉冲次数")
        self.pulse_sample_interval_edit = self._preset_combo(["1", "0.1", "0.01", "0.005", "0.002", "0.001"])
        self.pulse_upper_voltage_edit = self._line_edit("上限电压 / V")
        self.pulse_lower_voltage_edit = self._line_edit("下限电压 / V")
        self.pulse_pre_wait_edit = self._line_edit("点前等待 / s")
        self.pulse_tail_enabled_box = QCheckBox("脉冲结束后追加电压放电段", card)
        self.pulse_tail_current_mode_combo = NoWheelComboBox(card)
        self.pulse_tail_current_mode_combo.addItem("倍率", CurrentInputUiMode.RATE.value)
        self.pulse_tail_current_mode_combo.addItem("绝对电流", CurrentInputUiMode.ABSOLUTE.value)
        self.pulse_tail_rate_edit = self._line_edit("追加段倍率 / C")
        self.pulse_tail_current_edit = self._line_edit("追加段电流 / A")
        self.pulse_tail_manual_points_text = ""
        self.pulse_tail_points_button = self._button("编辑电压点", card)
        self.pulse_tail_points_status = QLabel("0 个值", card)
        self.pulse_tail_points_button.clicked.connect(self._edit_pulse_tail_voltage_points)
        tail_points_row = QHBoxLayout()
        tail_points_row.addWidget(self.pulse_tail_points_button)
        tail_points_row.addWidget(self.pulse_tail_points_status, 1)
        self.pulse_tail_points_wrap = QWidget(card)
        self.pulse_tail_points_wrap.setLayout(tail_points_row)
        self.pulse_tail_sample_interval_edit = self._preset_combo(["1", "0.1", "0.01", "0.005", "0.002", "0.001"])
        self.pulse_tail_insert_eis_box = QCheckBox("追加段每个电压点后插入 EIS", card)
        self.pulse_tail_section = QFrame(card)
        self.pulse_tail_section.setObjectName("subSection")
        self.pulse_tail_section_layout = QVBoxLayout(self.pulse_tail_section)
        self.pulse_tail_section_layout.setContentsMargins(14, 12, 14, 14)
        self.pulse_tail_section_layout.setSpacing(10)
        tail_title = QLabel("追加电压放电段", self.pulse_tail_section)
        tail_title.setObjectName("subSectionTitle")
        tail_hint = QLabel("所有脉冲结束后执行一次，按 CP 到目标电压并可插入 EIS。", self.pulse_tail_section)
        tail_hint.setObjectName("phaseHint")
        tail_hint.setWordWrap(True)
        self.pulse_tail_section_layout.addWidget(tail_title)
        self.pulse_tail_section_layout.addWidget(tail_hint)
        self.pulse_tail_form = QFormLayout()
        self.pulse_tail_section_layout.addLayout(self.pulse_tail_form)
        for label, field in (
            ("弛豫模式", self.pulse_relaxation_mode_combo),
            ("弛豫时间 / s", self.pulse_relaxation_time_edit),
            ("弛豫电流输入", self.pulse_relaxation_current_mode_combo),
            ("弛豫倍率 / C", self.pulse_relaxation_rate_edit),
            ("弛豫电流 / A", self.pulse_relaxation_current_edit),
            ("脉冲电流输入", self.pulse_current_mode_combo),
            ("脉冲倍率 / C", self.pulse_rate_edit),
            ("脉冲电流 / A", self.pulse_current_edit),
            ("脉冲时长 / s", self.pulse_duration_edit),
            ("脉冲次数", self.pulse_count_edit),
            ("采样间隔 / s", self.pulse_sample_interval_edit),
            ("上限电压 / V", self.pulse_upper_voltage_edit),
            ("下限电压 / V", self.pulse_lower_voltage_edit),
            ("点前等待 / s", self.pulse_pre_wait_edit),
            ("", self.pulse_tail_enabled_box),
        ):
            self.pulse_form.addRow(label, field)
        for label, field in (
            ("追加段电流输入", self.pulse_tail_current_mode_combo),
            ("追加段倍率 / C", self.pulse_tail_rate_edit),
            ("追加段电流 / A", self.pulse_tail_current_edit),
            ("追加段电压点", self.pulse_tail_points_wrap),
            ("追加段采样间隔 / s", self.pulse_tail_sample_interval_edit),
            ("", self.pulse_tail_insert_eis_box),
        ):
            self.pulse_tail_form.addRow(label, field)
        card.content_layout.addLayout(self.pulse_form)
        card.content_layout.addWidget(self.pulse_tail_section)
        return card

    def _build_impedance_card(self) -> Card:
        card = Card("阻抗参数", self, "默认使用 IMPFT；IMPSF 适合对照验证，通常更慢。")
        self.impedance_form = QFormLayout()
        self.use_open_circuit_init_e_box = QCheckBox("使用开路电位作为初始电位（Eoc）", card)
        self.impedance_measurement_mode_combo = NoWheelComboBox(card)
        self.impedance_measurement_mode_combo.addItem("FT 快速多频（推荐）", ImpedanceMeasurementMode.FT)
        self.impedance_measurement_mode_combo.addItem("SF 单频逐点（验证用）", ImpedanceMeasurementMode.SF)
        self.impedance_mode_hint = QLabel("SF 会逐频测量，通常比 FT 慢；建议只在验证 FT 结果时使用。", card)
        self.impedance_mode_hint.setObjectName("phaseHint")
        self.impedance_mode_hint.setWordWrap(True)
        self.init_e_v_edit = self._line_edit("手动初始电位 / V")
        self.high_frequency_edit = self._line_edit("高频 / Hz")
        self.low_frequency_edit = self._line_edit("低频 / Hz")
        self.amplitude_edit = self._line_edit("电压振幅 / V")
        self.quiet_time_edit = self._line_edit("静置时间 / s")
        self.impedance_form.addRow("", self.use_open_circuit_init_e_box)
        self.impedance_form.addRow("采集模式", self.impedance_measurement_mode_combo)
        self.impedance_form.addRow("", self.impedance_mode_hint)
        self.impedance_form.addRow("初始电位 / V", self.init_e_v_edit)
        self.impedance_form.addRow("高频 / Hz", self.high_frequency_edit)
        self.impedance_form.addRow("低频 / Hz", self.low_frequency_edit)
        self.impedance_form.addRow("电压振幅 / V", self.amplitude_edit)
        self.impedance_form.addRow("静置时间 / s", self.quiet_time_edit)
        card.content_layout.addLayout(self.impedance_form)
        return card

    def _button(self, text: str, parent: QWidget | None = None, *, primary: bool = False) -> PushButton:
        button = PrimaryPushButton(parent) if primary else PushButton(parent)
        button.setText(text)
        return button

    def _line_edit(self, placeholder: str) -> LineEdit:
        edit = LineEdit(self)
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
        edits = (
            self.scheme_name_edit,
            self.file_prefix_edit,
            self.export_dir_edit,
            self.active_material_edit,
            self.theoretical_capacity_edit,
            self.reference_rate_edit,
            self.reference_current_edit,
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
            self.pulse_tail_rate_edit,
            self.pulse_tail_current_edit,
        )
        for edit in edits:
            edit.textChanged.connect(self.schedule_refresh)
        for combo in (
            self.mode_combo,
            self.pulse_relaxation_mode_combo,
            self.pulse_relaxation_current_mode_combo,
            self.pulse_current_mode_combo,
            self.pulse_sample_interval_edit,
            self.pulse_tail_current_mode_combo,
            self.pulse_tail_sample_interval_edit,
            self.impedance_measurement_mode_combo,
        ):
            if isinstance(combo, PresetComboBox):
                combo.currentIndexChanged.connect(self.schedule_refresh)
                combo.lineEdit().textChanged.connect(self.schedule_refresh)
            else:
                combo.currentIndexChanged.connect(self.schedule_refresh)
        self.mode_combo.currentIndexChanged.connect(self._sync_workspace_mode)
        self.current_basis_mode_combo.currentIndexChanged.connect(self._sync_current_basis_visibility)
        self.current_basis_mode_combo.currentIndexChanged.connect(self.schedule_refresh)
        self.use_open_circuit_init_e_box.toggled.connect(self._sync_init_e_visibility)
        self.use_open_circuit_init_e_box.toggled.connect(self.schedule_refresh)
        self.pulse_relaxation_mode_combo.currentIndexChanged.connect(self._sync_pulse_field_visibility)
        self.pulse_relaxation_current_mode_combo.currentIndexChanged.connect(self._sync_pulse_field_visibility)
        self.pulse_current_mode_combo.currentIndexChanged.connect(self._sync_pulse_field_visibility)
        self.pulse_tail_enabled_box.toggled.connect(self._sync_pulse_field_visibility)
        self.pulse_tail_enabled_box.toggled.connect(self.schedule_refresh)
        self.pulse_tail_current_mode_combo.currentIndexChanged.connect(self._sync_pulse_field_visibility)
        self.pulse_tail_insert_eis_box.toggled.connect(self.schedule_refresh)
        self.export_dir_browse_button.clicked.connect(self._browse_export_directory)
        self.new_preset_button.clicked.connect(self.new_preset)
        self.open_preset_button.clicked.connect(self.open_preset)
        self.save_preset_button.clicked.connect(self.save_preset)
        self.save_as_preset_button.clicked.connect(self.save_preset_as)
        self.recent_presets_combo.currentIndexChanged.connect(self._open_selected_recent_preset)
        self.add_workstep_button.clicked.connect(lambda: self._append_phase(PhaseUiKind.TIME_POINTS))
        self.add_voltage_phase_button.clicked.connect(lambda: self._append_phase(PhaseUiKind.VOLTAGE_POINTS))
        self.add_rest_phase_button.clicked.connect(lambda: self._append_phase(PhaseUiKind.REST))
        self.create_loop_button.clicked.connect(self._create_loop_from_selection)

    def _apply_defaults(self) -> None:
        self._apply_state(GuiState())
        self._sync_current_basis_visibility()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget { color: #f5f5f7; font-family: 'Segoe UI Variable', 'Segoe UI', 'Microsoft YaHei UI', 'PingFang SC', sans-serif; font-size: 13px; }
            QWidget#workspacePage { background-color: #0b0b0f; }
            QWidget#leftPanel, QWidget#rightPanel, QScrollArea#leftScrollArea, QScrollArea#rightScrollArea, QWidget#leftScrollBody { background-color: #0b0b0f; }
            QScrollArea { border: none; }
            #cardWidget { background-color: #1d1d20; border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 18px; }
            #cardTitle { color: #f5f5f7; font-size: 16px; font-weight: 700; letter-spacing: 0.2px; }
            #cardSubtitle { color: #a1a1a6; font-size: 12px; line-height: 16px; }
            #fieldLabel, #panelLabel, #phaseHint { color: #a1a1a6; font-size: 12px; }
            QLabel { color: #f5f5f7; }
            QLineEdit, QTextEdit, QPlainTextEdit { background-color: #2c2c2e; border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 10px; padding: 7px 10px; selection-background-color: #0a84ff; }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #0a84ff; background-color: #303034; }
            ComboBox, EditableComboBox { min-height: 34px; border-radius: 10px; }
            #stepBadge { background-color: rgba(10, 132, 255, 0.16); color: #64d2ff; border: 1px solid rgba(100, 210, 255, 0.38); border-radius: 11px; font-weight: 700; padding: 5px 10px; }
            #metricPill { padding: 5px 12px; border-radius: 12px; background-color: rgba(10, 132, 255, 0.14); color: #64d2ff; border: 1px solid rgba(10, 132, 255, 0.30); }
            #summaryPanel { background-color: #151518; border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 14px; padding: 10px; }
            #subSection { background-color: #151518; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; }
            #subSectionTitle { color: #f5f5f7; font-size: 13px; font-weight: 700; }
            QFrame[workstepRow="true"] { background-color: #17171a; border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 16px; }
            QFrame[workstepRow="true"]:hover { border: 1px solid rgba(10, 132, 255, 0.42); background-color: #1c1c20; }
            QCheckBox { spacing: 8px; color: #f5f5f7; }
            QCheckBox::indicator { width: 16px; height: 16px; border-radius: 5px; border: 1px solid rgba(255, 255, 255, 0.26); background-color: #2c2c2e; }
            QCheckBox::indicator:checked { background-color: #0a84ff; border: 1px solid #0a84ff; }
            """
        )

    def _make_default_phase(self, kind: PhaseUiKind, index: int) -> GuiPhaseState:
        names = {
            PhaseUiKind.TIME_POINTS: "时间工步",
            PhaseUiKind.VOLTAGE_POINTS: "电压工步",
            PhaseUiKind.REST: "静置工步",
        }
        return GuiPhaseState(label=f"{names[kind]} {index}", phase_kind=kind)

    def _collect_workflow_items(self) -> list[WorkflowItemState]:
        items: list[WorkflowItemState] = []
        for widget in self.workflow_widgets:
            items.append(widget.collect_state())
        return items

    def _rebuild_workflow_widgets(self, items: list[WorkflowItemState]) -> None:
        while self.phase_layout.count():
            item = self.phase_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.workflow_widgets.clear()
        self.phase_editors.clear()
        if not items:
            items = [GuiPhaseState()]
        for index, item in enumerate(items, start=1):
            if isinstance(item, GuiLoopState):
                widget = LoopBlockWidget(
                    index,
                    item,
                    on_change=self.schedule_refresh,
                    on_move_up=self._move_loop_up,
                    on_move_down=self._move_loop_down,
                    on_delete=self._delete_loop,
                    on_duplicate=self._duplicate_loop,
                    parent=self.phase_container,
                )
            else:
                widget = WorkstepEditorRow(
                    index,
                    item,
                    on_change=self.schedule_refresh,
                    on_move_up=self._move_phase_up,
                    on_move_down=self._move_phase_down,
                    on_delete=self._delete_phase,
                    parent=self.phase_container,
                )
                self.phase_editors.append(widget)
            self.phase_layout.addWidget(widget)
            self.workflow_widgets.append(widget)
        self._sync_workflow_order_state()

    def _sync_workflow_order_state(self) -> None:
        total = len(self.workflow_widgets)
        self.phase_editors = [widget for widget in self.workflow_widgets if isinstance(widget, WorkstepEditorRow)]
        for index, widget in enumerate(self.workflow_widgets, start=1):
            widget.set_order_state(index, total)

    def _append_phase(self, kind: PhaseUiKind) -> None:
        items = self._collect_workflow_items()
        flat_index = len(expand_workflow_items(items)) + 1
        items.append(self._make_default_phase(kind, flat_index))
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _move_phase_up(self, row: WorkstepEditorRow) -> None:
        index = self.workflow_widgets.index(row)
        if index <= 0:
            return
        items = self._collect_workflow_items()
        items[index - 1], items[index] = items[index], items[index - 1]
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _move_phase_down(self, row: WorkstepEditorRow) -> None:
        index = self.workflow_widgets.index(row)
        if index >= len(self.workflow_widgets) - 1:
            return
        items = self._collect_workflow_items()
        items[index + 1], items[index] = items[index], items[index + 1]
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _delete_phase(self, row: WorkstepEditorRow) -> None:
        if len(self.workflow_widgets) <= 1:
            return
        index = self.workflow_widgets.index(row)
        items = self._collect_workflow_items()
        del items[index]
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _move_loop_up(self, loop: LoopBlockWidget) -> None:
        index = self.workflow_widgets.index(loop)
        if index <= 0:
            return
        items = self._collect_workflow_items()
        items[index - 1], items[index] = items[index], items[index - 1]
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _move_loop_down(self, loop: LoopBlockWidget) -> None:
        index = self.workflow_widgets.index(loop)
        if index >= len(self.workflow_widgets) - 1:
            return
        items = self._collect_workflow_items()
        items[index + 1], items[index] = items[index], items[index + 1]
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _delete_loop(self, loop: LoopBlockWidget) -> None:
        if len(self.workflow_widgets) <= 1:
            return
        index = self.workflow_widgets.index(loop)
        items = self._collect_workflow_items()
        del items[index]
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _duplicate_loop(self, loop: LoopBlockWidget) -> None:
        index = self.workflow_widgets.index(loop)
        items = self._collect_workflow_items()
        items.insert(index + 1, loop.collect_state().model_copy(deep=True))
        self._rebuild_workflow_widgets(items)
        self.schedule_refresh()

    def _create_loop_from_selection(self) -> None:
        selected_indexes = [index for index, widget in enumerate(self.workflow_widgets) if isinstance(widget, WorkstepEditorRow) and widget.is_selected()]
        if len(selected_indexes) < 2:
            self.statusBar().showMessage("至少选择两个连续工步才能创建循环块。")
            return
        if selected_indexes != list(range(selected_indexes[0], selected_indexes[-1] + 1)):
            self.statusBar().showMessage("循环块只能由连续工步创建。")
            return
        items = self._collect_workflow_items()
        phases = [items[index] for index in selected_indexes]
        if any(isinstance(item, GuiLoopState) for item in phases):
            self.statusBar().showMessage("当前版本不支持嵌套循环块。")
            return
        loop = GuiLoopState(label=f"循环块 {selected_indexes[0] + 1}", repeat_count=2, phases=[item.model_copy(deep=True) for item in phases if isinstance(item, GuiPhaseState)])
        updated = items[: selected_indexes[0]] + [loop] + items[selected_indexes[-1] + 1 :]
        self._rebuild_workflow_widgets(updated)
        self.schedule_refresh()

    def _collect_state(self) -> GuiState:
        workflow_items = self._collect_workflow_items()
        return GuiState.model_validate(
            {
                "workspace_mode": self.mode_combo.currentData(),
                "scheme_name": self.scheme_name_edit.text() or "CHI 原位阻抗",
                "file_prefix": self.file_prefix_edit.text() or "CHI",
                "export_dir": self.export_dir_edit.text(),
                "active_material_mg": self.active_material_edit.text() or "1",
                "theoretical_capacity_mah_mg": self.theoretical_capacity_edit.text() or "865",
                "current_basis_mode": self.current_basis_mode_combo.currentData(),
                "reference_rate_c": self.reference_rate_edit.text() or "1",
                "reference_current_a": self.reference_current_edit.text() or "0.000865",
                "workflow_items": workflow_items,
                "phases": expand_workflow_items(workflow_items),
                "use_open_circuit_init_e": self.use_open_circuit_init_e_box.isChecked(),
                "init_e_v": self.init_e_v_edit.text() or "3.2",
                "high_frequency_hz": self.high_frequency_edit.text() or "100000",
                "low_frequency_hz": self.low_frequency_edit.text() or "0.01",
                "amplitude_v": self.amplitude_edit.text() or "0.005",
                "quiet_time_s": self.quiet_time_edit.text() or "2",
                "impedance_measurement_mode": self.impedance_measurement_mode_combo.currentData(),
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
                "pulse_sample_interval_s": self.pulse_sample_interval_edit.currentText() or "1",
                "pulse_upper_voltage_v": self.pulse_upper_voltage_edit.text() or "4",
                "pulse_lower_voltage_v": self.pulse_lower_voltage_edit.text() or "-1",
                "pulse_pre_wait_s": self.pulse_pre_wait_edit.text() or "0",
                "pulse_tail_enabled": self.pulse_tail_enabled_box.isChecked(),
                "pulse_tail_current_mode": self.pulse_tail_current_mode_combo.currentData(),
                "pulse_tail_rate_c": self.pulse_tail_rate_edit.text() or "0.1",
                "pulse_tail_current_a": self.pulse_tail_current_edit.text() or "0.0000865",
                "pulse_tail_manual_points_text": self.pulse_tail_manual_points_text,
                "pulse_tail_sample_interval_s": self.pulse_tail_sample_interval_edit.currentText() or "1",
                "pulse_tail_insert_eis": self.pulse_tail_insert_eis_box.isChecked(),
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
            self.current_basis_mode_combo.setCurrentIndex(self.current_basis_mode_combo.findData(state.current_basis_mode.value))
            self.reference_rate_edit.setText(state.reference_rate_c)
            self.reference_current_edit.setText(state.reference_current_a)
            self._rebuild_workflow_widgets(state.workflow_items)
            self.use_open_circuit_init_e_box.setChecked(state.use_open_circuit_init_e)
            self.init_e_v_edit.setText(state.init_e_v)
            self.high_frequency_edit.setText(state.high_frequency_hz)
            self.low_frequency_edit.setText(state.low_frequency_hz)
            self.amplitude_edit.setText(state.amplitude_v)
            self.quiet_time_edit.setText(state.quiet_time_s)
            self.impedance_measurement_mode_combo.setCurrentIndex(self.impedance_measurement_mode_combo.findData(state.impedance_measurement_mode.value))
            self.pulse_relaxation_mode_combo.setCurrentIndex(self.pulse_relaxation_mode_combo.findData(state.pulse_relaxation_mode.value))
            self.pulse_relaxation_time_edit.setText(state.pulse_relaxation_time_s)
            self.pulse_relaxation_current_mode_combo.setCurrentIndex(self.pulse_relaxation_current_mode_combo.findData(state.pulse_relaxation_current_mode.value))
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
            self.pulse_tail_enabled_box.setChecked(state.pulse_tail_enabled)
            self.pulse_tail_current_mode_combo.setCurrentIndex(self.pulse_tail_current_mode_combo.findData(state.pulse_tail_current_mode.value))
            self.pulse_tail_rate_edit.setText(state.pulse_tail_rate_c)
            self.pulse_tail_current_edit.setText(state.pulse_tail_current_a)
            self.pulse_tail_manual_points_text = state.pulse_tail_manual_points_text
            self._refresh_pulse_tail_points_status()
            self.pulse_tail_sample_interval_edit.setEditText(state.pulse_tail_sample_interval_s)
            self.pulse_tail_insert_eis_box.setChecked(state.pulse_tail_insert_eis)
        finally:
            self._updating_ui = False
        self._sync_workspace_mode()
        self._sync_current_basis_visibility()
        self._sync_init_e_visibility()
        self._sync_pulse_field_visibility()
        self.refresh_preview()

    def _sync_workspace_mode(self) -> None:
        is_sequence = self.mode_combo.currentData() == WorkspaceMode.SEQUENCE.value
        self.workstep_card.setVisible(is_sequence)
        self.pulse_card.setVisible(not is_sequence)
        self.workspace_mode_label.setText("序列模式" if is_sequence else "脉冲模式")
        self.workspace_headline.setText("工步可组合成循环块并在生成前展开。" if is_sequence else "脉冲参数单独编辑。")
        self.workspace_copy.setText("范围电压取点会自动补终点；非均匀取点请使用手动列表。" if is_sequence else "脉冲模式已移除持续原位分支。")
        self._refresh_workstep_metrics()

    def _sync_init_e_visibility(self) -> None:
        visible = not self.use_open_circuit_init_e_box.isChecked()
        label = self.impedance_form.labelForField(self.init_e_v_edit)
        if label is not None:
            label.setVisible(visible)
        self.init_e_v_edit.setVisible(visible)

    def _sync_current_basis_visibility(self) -> None:
        visible = self.current_basis_mode_combo.currentData() == CurrentBasisUiMode.REFERENCE.value
        for widget in (self.reference_rate_edit, self.reference_current_edit):
            label = self.battery_form.labelForField(widget)
            if label is not None:
                label.setVisible(visible)
            widget.setVisible(visible)
        self.current_basis_value.setText("用已知倍率和对应电流反推 1C。" if visible else "半电池通常直接按材料参数换算 1C。")

    def _edit_pulse_tail_voltage_points(self) -> None:
        dialog = GuidedManualPointDialog(
            title="编辑追加段电压点",
            text=self.pulse_tail_manual_points_text,
            is_voltage=True,
            direction=ProcessDirection.DISCHARGE,
            parent=self,
        )
        if dialog.exec():
            self.pulse_tail_manual_points_text = dialog.value()
            self._refresh_pulse_tail_points_status()
            self.schedule_refresh()

    def _refresh_pulse_tail_points_status(self) -> None:
        values = parse_float_list(self.pulse_tail_manual_points_text)
        if not values:
            self.pulse_tail_points_status.setText("0 个值")
            return
        self.pulse_tail_points_status.setText(f"{len(values)} 个值 · {values[0]:g} → {values[-1]:g} V")

    def _sync_pulse_field_visibility(self) -> None:
        relaxation_mode_is_cc = self.pulse_relaxation_mode_combo.currentData() == RelaxationUiMode.CONSTANT_CURRENT.value
        pulse_mode_is_absolute = self.pulse_current_mode_combo.currentData() == CurrentInputUiMode.ABSOLUTE.value
        relaxation_mode_is_absolute = self.pulse_relaxation_current_mode_combo.currentData() == CurrentInputUiMode.ABSOLUTE.value
        tail_enabled = self.pulse_tail_enabled_box.isChecked()
        tail_mode_is_absolute = self.pulse_tail_current_mode_combo.currentData() == CurrentInputUiMode.ABSOLUTE.value
        self._set_form_row_visible(self.pulse_form, self.pulse_relaxation_current_mode_combo, relaxation_mode_is_cc)
        self._set_form_row_visible(self.pulse_form, self.pulse_relaxation_rate_edit, relaxation_mode_is_cc and not relaxation_mode_is_absolute)
        self._set_form_row_visible(self.pulse_form, self.pulse_relaxation_current_edit, relaxation_mode_is_cc and relaxation_mode_is_absolute)
        self._set_form_row_visible(self.pulse_form, self.pulse_rate_edit, not pulse_mode_is_absolute)
        self._set_form_row_visible(self.pulse_form, self.pulse_current_edit, pulse_mode_is_absolute)
        for widget in (
            self.pulse_tail_current_mode_combo,
            self.pulse_tail_points_wrap,
            self.pulse_tail_sample_interval_edit,
            self.pulse_tail_insert_eis_box,
        ):
            self._set_form_row_visible(self.pulse_tail_form, widget, tail_enabled)
        self._set_form_row_visible(self.pulse_tail_form, self.pulse_tail_rate_edit, tail_enabled and not tail_mode_is_absolute)
        self._set_form_row_visible(self.pulse_tail_form, self.pulse_tail_current_edit, tail_enabled and tail_mode_is_absolute)
        self.pulse_tail_section.setVisible(tail_enabled)

    def _set_form_row_visible(self, form: QFormLayout, widget: QWidget, visible: bool) -> None:
        label = form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)
        widget.setVisible(visible)

    def _refresh_workstep_metrics(self, bundle: ScriptBundle | None = None) -> None:
        if self.mode_combo.currentData() != WorkspaceMode.SEQUENCE.value:
            self.workstep_count_pill.setText("脉冲模式")
            self.total_points_pill.setText("0 点")
            self.total_eis_pill.setText("0 次 EIS")
            return
        if isinstance(bundle, SequenceScriptBundle):
            workstep_count = len(bundle.phase_plans)
            total_points = bundle.total_point_count
            total_eis = bundle.total_eis_count
        else:
            state = self._collect_state()
            workstep_count = len(state.phases)
            total_points = 0
            total_eis = 0
        self.workstep_count_pill.setText(f"{workstep_count} 个工步")
        self.total_points_pill.setText(f"{total_points} 点")
        self.total_eis_pill.setText(f"{total_eis} 次 EIS")

    def schedule_refresh(self, *_: object) -> None:
        if not self._updating_ui:
            self._refresh_timer.start()

    def refresh_preview(self, *_: object) -> None:
        if self._updating_ui:
            return
        try:
            state = self._collect_state()
            bundle = self._backend.preview(state)
            self._last_bundle = bundle
            self.issue_list.set_issues(bundle.issues)
            self.preview_chart.set_bundle(bundle)
            self.output_panel.set_scripts(bundle.commented_script, bundle.minimal_script, "\n".join(bundle.summary_lines), bundle.can_generate)
            self._update_current_preview(state)
            self._refresh_workstep_metrics(bundle)
            self.planning_card.setVisible(
                isinstance(bundle, SequenceScriptBundle)
                and bundle.lost_checkpoint_count > 0
                and self.mode_combo.currentData() == WorkspaceMode.SEQUENCE.value
            )
            self._update_status_bar(bundle)
        except Exception as exc:  # pragma: no cover
            issue = ValidationIssue(severity=Severity.ERROR, code="ui.refresh", message=str(exc))
            self._last_bundle = None
            self.issue_list.set_issues([issue])
            self.preview_chart.set_bundle(None)
            self.output_panel.set_scripts("", "", str(exc), False)
            self._refresh_workstep_metrics()
            self.statusBar().showMessage(f"预览失败：{exc}")

    def _update_current_preview(self, state: GuiState) -> None:
        try:
            one_c_current_a, operating_current_a, operating_rate_c = self._backend.resolve_current_preview(state)
        except Exception:
            self.current_basis_value.setText("-")
            self.current_operating_value.setText("-")
            self.current_preview_label.setText("-")
            return
        basis_text = "参考基准" if state.current_basis_mode is CurrentBasisUiMode.REFERENCE else "材料基准"
        self.current_basis_value.setText(f"{basis_text} | 1C = {one_c_current_a:.9f} A")
        self.current_operating_value.setText(f"{operating_current_a:.9f} A | {operating_rate_c:g} C")
        self.current_preview_label.setText(f"当前：{operating_current_a:.9g} A | {operating_rate_c:g} C\n1C：{one_c_current_a:.9g} A")

    def _update_status_bar(self, bundle: ScriptBundle) -> None:
        error_count = sum(1 for issue in bundle.issues if issue.severity is Severity.ERROR)
        warning_count = sum(1 for issue in bundle.issues if issue.severity is Severity.WARNING)
        if isinstance(bundle, SequenceScriptBundle) and bundle.lost_checkpoint_count:
            self.statusBar().showMessage(f"错误 {error_count} | 警告 {warning_count} | 丢点 {bundle.lost_checkpoint_count}")
        else:
            self.statusBar().showMessage(f"错误 {error_count} | 警告 {warning_count}")

    def _browse_export_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择导出目录", self.export_dir_edit.text() or str(Path.cwd()))
        if directory:
            self.export_dir_edit.setText(directory)

    def new_preset(self) -> None:
        self._current_preset_path = None
        self._apply_state(GuiState())

    def open_preset(self) -> None:
        base_dir = self._current_preset_path.parent if self._current_preset_path else Path.cwd()
        path, _ = QFileDialog.getOpenFileName(self, "打开预设", str(base_dir), "CHI 预设 (*.chi-preset)")
        if path:
            self.load_preset_from_path(path)

    def save_preset(self) -> None:
        if self._current_preset_path is None:
            self.save_preset_as()
        else:
            self.save_preset_to_path(self._current_preset_path)

    def save_preset_as(self) -> None:
        default_path = self._current_preset_path or (Path.cwd() / "workflow.chi-preset")
        path, _ = QFileDialog.getSaveFileName(self, "保存预设", str(default_path), "CHI 预设 (*.chi-preset)")
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

    def _update_recent_presets(self) -> None:
        current_path = self.recent_presets_combo.currentData()
        self.recent_presets_combo.blockSignals(True)
        self.recent_presets_combo.clear()
        self.recent_presets_combo.addItem("最近预设", "")
        for path in self._preset_service.load_recent_files():
            self.recent_presets_combo.addItem(path.name, str(path))
        index = self.recent_presets_combo.findData(current_path) if current_path else 0
        self.recent_presets_combo.setCurrentIndex(index if index >= 0 else 0)
        self.recent_presets_combo.blockSignals(False)

    def _open_selected_recent_preset(self) -> None:
        path = self.recent_presets_combo.currentData()
        if path:
            self.load_preset_from_path(path)


__all__ = ["MainWindow"]
