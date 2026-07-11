"""Prominent domain issue presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem, QWidget
from qfluentwidgets import ListWidget

from chi_generator.domain.models import RiskLevel, Severity, ValidationIssue


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
        "target_voltage_unreachable": "目标电压可能已被瞬时极化越过。",
        "target_voltage_long_rest": "长静置后再定电位可能改变电池状态。",
        "target_voltage_dense_low_frequency": "多点低频目标电压 PEIS 可能导致状态漂移。",
        "voltage_trigger_eio_meaning": "目标电压仅作为 CP 触发条件。",
        "voltage_trigger_eio_many_long_rest": "长静置多点 eio 会叠加弛豫和再极化历史。",
        "dod_planned_capacity_basis": "DOD 按容量基准规划，实际 DOD 需后处理校正。",
        "dod_cutoff_limit": "100% DOD 可能先触发截止电压。",
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
        "voltage_trigger_eio_meaning": "EIS 实际在静置后的 OCV 附近进行。",
        "dod_cutoff_limit": "建议考虑只做到 80% DOD，或单独保存截止状态。",
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


__all__ = ["IssueListWidget"]

