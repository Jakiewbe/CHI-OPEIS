"""Orchestration facade for typed CHI script generation."""

from __future__ import annotations

from .models import (
    ExperimentRequest,
    ExperimentSequenceRequest,
    PhaseKind,
    ProcessDirection,
    ScriptBundle,
    ScriptKind,
    SequenceScriptBundle,
    TimeBasisMode,
)
from .rendering import render_pulse_request, render_sequence_request, wrap_commented_script
from .validation import validate_request, validate_sequence_request


def _phase_kind_text(kind: PhaseKind) -> str:
    return {
        PhaseKind.TIME_POINTS: "时间取点",
        PhaseKind.VOLTAGE_POINTS: "电压取点",
        PhaseKind.REST: "静置工步",
    }[kind]


def _direction_text(direction: ProcessDirection | None) -> str:
    if direction is None:
        return "-"
    return "充电" if direction is ProcessDirection.CHARGE else "放电"


class ScriptGenerationService:
    """Pure domain facade used by the GUI."""

    def preview(self, request: ExperimentSequenceRequest | ExperimentRequest) -> ScriptBundle:
        return self.generate(request)

    def generate(self, request: ExperimentSequenceRequest | ExperimentRequest) -> ScriptBundle:
        if isinstance(request, ExperimentSequenceRequest):
            return self._generate_sequence(request)
        if request.kind is ScriptKind.PULSE:
            return self._generate_pulse(request)
        raise ValueError(f"legacy request kind {request.kind.value} is no longer supported")

    def _generate_sequence(self, request: ExperimentSequenceRequest) -> SequenceScriptBundle:
        validation = validate_sequence_request(request)
        issues = [*validation.errors, *validation.warnings]
        minimal_lines, summary = render_sequence_request(request) if validation.can_generate else ([], {})
        summary_lines = self._build_sequence_summary_lines(request, summary)
        commented_script = wrap_commented_script(summary_lines=summary_lines, script_lines=minimal_lines, issues=issues)
        minimal_script = "\n".join(minimal_lines)
        return SequenceScriptBundle(
            commented_script=commented_script if validation.can_generate else "",
            minimal_script=minimal_script if validation.can_generate else "",
            issues=issues,
            one_c_current_a=summary.get("one_c_current_a"),
            estimated_eis_duration_s=summary.get("estimated_eis_duration_s"),
            summary_lines=summary_lines,
            phase_plans=list(summary.get("phase_plans", [])),
            total_wall_clock_s=float(summary.get("total_wall_clock_s", 0.0)),
            total_point_count=int(summary.get("total_point_count", 0)),
            total_eis_count=int(summary.get("total_eis_count", 0)),
            soc_trace=list(summary.get("soc_trace", [])),
            soc_zero_time_s=summary.get("soc_zero_time_s"),
            lost_checkpoint_count=int(summary.get("lost_checkpoint_count", 0)),
        )

    def _generate_pulse(self, request: ExperimentRequest) -> ScriptBundle:
        validation = validate_request(request)
        issues = [*validation.errors, *validation.warnings]
        minimal_lines, summary = render_pulse_request(request) if validation.can_generate else ([], {})
        summary_lines = self._build_pulse_summary_lines(request, summary)
        commented_script = wrap_commented_script(summary_lines=summary_lines, script_lines=minimal_lines, issues=issues)
        return ScriptBundle(
            kind=ScriptKind.PULSE,
            commented_script=commented_script if validation.can_generate else "",
            minimal_script="\n".join(minimal_lines) if validation.can_generate else "",
            issues=issues,
            one_c_current_a=summary.get("one_c_current_a"),
            estimated_eis_duration_s=summary.get("estimated_eis_duration_s"),
            summary_lines=summary_lines,
        )

    def _build_sequence_summary_lines(self, request: ExperimentSequenceRequest, summary: dict[str, object]) -> list[str]:
        phase_plans = list(summary.get("phase_plans", []))
        total_points = int(summary.get("total_point_count", 0))
        total_eis = int(summary.get("total_eis_count", 0))
        lost_checkpoint_count = int(summary.get("lost_checkpoint_count", 0))
        lines = [
            f"方案名称：{request.project.scheme_name}",
            f"文件前缀：{request.project.file_prefix}",
            f"导出目录：{request.project.export_dir}",
            f"工步数量：{len(request.phases)}",
            f"总取点数：{total_points}",
            f"EIS 总数：{total_eis}",
            f"单次 EIS 预估时长：{float(summary.get('estimated_eis_duration_s', 0.0)):.0f} s",
        ]
        if summary.get("one_c_current_a") is not None:
            lines.append(f"1C 电流：{summary['one_c_current_a']:.9f} A")
        if summary.get("soc_zero_time_s") is not None:
            lines.append(f"SoC 预计归零时间：{float(summary['soc_zero_time_s']) / 60.0:.2f} min")
        lines.append(f"SoC 耗尽后的丢点数：{lost_checkpoint_count}")

        for plan in phase_plans:
            lines.append(f"{plan.phase_index}. {plan.label} | {_phase_kind_text(plan.phase_kind)} | {_direction_text(plan.direction)}")
            if plan.phase_kind is PhaseKind.TIME_POINTS:
                basis_text = {
                    TimeBasisMode.ACTIVE_PROGRESS: "有效进度",
                    TimeBasisMode.INTERRUPTION_COMPENSATED: "中断补偿",
                    TimeBasisMode.CAPACITY_COMPENSATED: "等效容量补偿",
                }.get(plan.time_basis_mode, "有效进度")
                mode_text = {
                    "fixed": "固定取点",
                    "segmented": "分段取点",
                    "manual": "手动列表",
                }.get(plan.sampling_mode.value if plan.sampling_mode is not None else "segmented", "分段取点")
                lines.append(
                    f"  采样：{mode_text} | {basis_text} | {plan.point_count} 点 | {plan.eis_count} 次 EIS | {plan.wall_clock_total_s / 60.0:.1f} min"
                )
                if plan.compensation_offsets_min:
                    label = "容量补偿偏移（min）" if plan.time_basis_mode is TimeBasisMode.CAPACITY_COMPENSATED else "补偿偏移（min）"
                    lines.append(f"  {label}： " + ", ".join(f"{value:g}" for value in plan.compensation_offsets_min))
            elif plan.phase_kind is PhaseKind.VOLTAGE_POINTS:
                mode_text = {
                    "linear": "范围生成",
                    "manual": "手动列表",
                }.get(plan.sampling_mode.value if plan.sampling_mode is not None else "linear", "范围生成")
                lines.append(f"  采样：{mode_text} | {plan.point_count} 点 | {plan.eis_count} 次 EIS | {plan.wall_clock_total_s / 60.0:.1f} min")
            else:
                lines.append(f"  静置：{plan.wall_clock_total_s:g} s")
            if plan.lost_eis_marker_times_s:
                lines.append("  丢失点位（min）： " + ", ".join(f"{value / 60.0:g}" for value in plan.lost_eis_marker_times_s))

        lines.append(f"总历时：{float(summary.get('total_wall_clock_s', 0.0)) / 60.0:.2f} min")
        return lines

    def _build_pulse_summary_lines(self, request: ExperimentRequest, summary: dict[str, object]) -> list[str]:
        lines = [
            f"方案名称：{request.project.scheme_name}",
            f"文件前缀：{request.project.file_prefix}",
            f"导出目录：{request.project.export_dir}",
            f"脉冲次数：{summary.get('pulse_count', 0)}",
        ]
        if summary.get("one_c_current_a") is not None:
            lines.append(f"1C 电流：{summary['one_c_current_a']:.9f} A")
        if summary.get("estimated_eis_duration_s") is not None:
            lines.append(f"单次 EIS 预估时长：{float(summary['estimated_eis_duration_s']):.0f} s")
        return lines


__all__ = ["ScriptGenerationService"]
