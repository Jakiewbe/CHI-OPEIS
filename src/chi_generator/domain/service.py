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
    TimePointPhase,
)
from .rendering import render_pulse_request, render_sequence_request, wrap_commented_script
from .validation import validate_request, validate_sequence_request


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
            summary_lines=summary_lines,
            phase_plans=list(summary.get("phase_plans", [])),
            total_wall_clock_s=float(summary.get("total_wall_clock_s", 0.0)),
            total_point_count=int(summary.get("total_point_count", 0)),
            total_eis_count=int(summary.get("total_eis_count", 0)),
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
            summary_lines=summary_lines,
        )

    def _build_sequence_summary_lines(self, request: ExperimentSequenceRequest, summary: dict[str, object]) -> list[str]:
        phase_plans = list(summary.get("phase_plans", []))
        total_points = int(summary.get("total_point_count", 0))
        total_eis = int(summary.get("total_eis_count", 0))
        lines = [
            f"方案名称: {request.project.scheme_name}",
            f"命名前缀: {request.project.file_prefix}",
            f"导出目录: {request.project.export_dir}",
            f"工步数: {len(request.phases)}",
            f"总取点数: {total_points}",
            f"总 EIS 次数: {total_eis}",
        ]
        if summary.get("one_c_current_a") is not None:
            lines.append(f"1C 电流(A): {summary['one_c_current_a']:.9f}")

        for phase_model, plan in zip(request.phases, phase_plans):
            direction_text = "-" if plan.direction is None else ("充电" if plan.direction is ProcessDirection.CHARGE else "放电")
            lines.append(f"{plan.phase_index}. {plan.label} | {plan.phase_kind.value} | {direction_text}")
            if plan.phase_kind is PhaseKind.TIME_POINTS:
                assert isinstance(phase_model, TimePointPhase)
                basis_text = "中断补偿" if phase_model.time_points.time_basis_mode is TimeBasisMode.INTERRUPTION_COMPENSATED else "有效进度累计"
                lines.append(f"时间基准: {basis_text}")
                lines.append(f"取点数: {plan.point_count}")
                lines.append(f"EIS 次数: {plan.eis_count}")
                lines.append("等效时间点(min): " + ", ".join(f"{value:g}" for value in plan.effective_points))
                lines.append("脚本累计时间(min): " + ", ".join(f"{value:g}" for value in plan.rendered_points))
                if plan.compensation_offsets_min:
                    lines.append("补偿偏移(min): " + ", ".join(f"{value:g}" for value in plan.compensation_offsets_min))
                    lines.append(f"补偿总时长(s): {plan.compensation_offsets_min[-1] * 60.0:g}")
            elif plan.phase_kind is PhaseKind.VOLTAGE_POINTS:
                lines.append(f"取点数: {plan.point_count}")
                lines.append(f"EIS 次数: {plan.eis_count}")
                lines.append("电压点(V): " + ", ".join(f"{value:.2f}".rstrip("0").rstrip(".") for value in plan.effective_points))
            else:
                lines.append(f"静置时长(s): {plan.wall_clock_total_s:g}")
            lines.append(f"阶段预计墙钟时长(min): {plan.wall_clock_total_s / 60.0:.2f}".rstrip("0").rstrip("."))

        lines.append(f"预计墙钟总时长(min): {(float(summary.get('total_wall_clock_s', 0.0)) / 60.0):.2f}".rstrip("0").rstrip("."))
        return lines

    def _build_pulse_summary_lines(self, request: ExperimentRequest, summary: dict[str, object]) -> list[str]:
        lines = [
            f"方案名称: {request.project.scheme_name}",
            f"命名前缀: {request.project.file_prefix}",
            f"导出目录: {request.project.export_dir}",
            f"脉冲次数: {summary.get('pulse_count', 0)}",
        ]
        if summary.get("one_c_current_a") is not None:
            lines.append(f"1C 电流(A): {summary['one_c_current_a']:.9f}")
        return lines


__all__ = ["ScriptGenerationService"]
