"""Validation rules for CHI planning requests."""

from __future__ import annotations

from .calculations import plan_time_points, plan_voltage_points
from .models import (
    ExperimentRequest,
    ExperimentSequenceRequest,
    RestPhase,
    ScriptKind,
    Severity,
    TimeBasisMode,
    TimePointPhase,
    ValidationIssue,
    ValidationResult,
    VoltagePointPhase,
)


INTERRUPTION_WARNING_THRESHOLD = 6
FREQUENT_DIRECTION_SWITCH_THRESHOLD = 3


def validate_sequence_request(request: ExperimentSequenceRequest) -> ValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    if not request.phases:
        errors.append(ValidationIssue(severity=Severity.ERROR, code="missing_phases", field="phases", message="至少需要一个工步。"))
        return ValidationResult(errors=errors, warnings=warnings)

    direction_switches = 0
    previous_direction = None
    total_eis_points = 1
    total_compensation_s = 0.0
    total_rest_s = 0.0
    total_progress_s = 0.0

    for index, phase in enumerate(request.phases, start=1):
        field = f"phases[{index - 1}]"
        try:
            if isinstance(phase, RestPhase):
                total_rest_s += phase.duration_s
                continue

            if previous_direction is not None and previous_direction is not phase.direction:
                direction_switches += 1
            previous_direction = phase.direction

            if isinstance(phase, TimePointPhase):
                plan = plan_time_points(phase.time_points)
                total_progress_s += (plan.actual_points[-1] * 60.0) if plan.actual_points else 0.0
                total_compensation_s += plan.compensation_total * 60.0
                if phase.insert_eis_after_each_point:
                    total_eis_points += len(plan.points)
            elif isinstance(phase, VoltagePointPhase):
                plan = plan_voltage_points(phase.voltage_points, direction=phase.direction)
                if max(plan.points) > phase.voltage_window.upper_v or min(plan.points) < phase.voltage_window.lower_v:
                    raise ValueError("voltage points must remain within the configured safety voltage window")
                if phase.insert_eis_after_each_point:
                    total_eis_points += len(plan.points)
        except ValueError as exc:
            errors.append(ValidationIssue(severity=Severity.ERROR, code="phase_invalid", field=field, message=str(exc)))

    if errors:
        return ValidationResult(errors=errors, warnings=warnings)

    if request.impedance_defaults.low_frequency_hz == 0.01 and total_eis_points >= 6:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="dense_eis_low_frequency",
                field="impedance_defaults.low_frequency_hz",
                message="EIS 点位较多且 fl=0.01 Hz，单次实验时长可能明显增加。",
                hint="如无必须覆盖极低频的需求，可提高 fl 或减少取点数。",
            )
        )

    if total_eis_points >= INTERRUPTION_WARNING_THRESHOLD:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="interrupted_progress",
                field="phases",
                message="整条序列中的 EIS 插入次数较多，实验曲线会出现明显中断。",
                hint="可减少取点密度，或只在关键工步开启 EIS。",
            )
        )

    if total_compensation_s >= 600:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="high_compensation_total",
                field="phases",
                message="中断补偿累计时间较长，后段脚本会被明显拉长。",
                hint=f"当前累计补偿约 {total_compensation_s / 60.0:.1f} min。",
            )
        )

    if direction_switches >= FREQUENT_DIRECTION_SWITCH_THRESHOLD:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="frequent_direction_switches",
                field="phases",
                message="工步方向切换较频繁，请确认这符合实际实验工艺。",
            )
        )

    if total_rest_s > total_progress_s and total_rest_s > 0:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="rest_dominates_sequence",
                field="phases",
                message="静置总时长已经超过电化学工作工步时长，请确认是否为预期配置。",
            )
        )

    return ValidationResult(errors=errors, warnings=warnings)


def validate_request(request: ExperimentRequest) -> ValidationResult:
    if request.kind is ScriptKind.PULSE:
        errors: list[ValidationIssue] = []
        if request.pulse is None:
            errors.append(ValidationIssue(severity=Severity.ERROR, code="missing_pulse", field="pulse", message="脉冲模式需要提供脉冲配置。"))
        return ValidationResult(errors=errors, warnings=[])
    return ValidationResult()


validate_experiment_request = validate_request


__all__ = [
    "FREQUENT_DIRECTION_SWITCH_THRESHOLD",
    "INTERRUPTION_WARNING_THRESHOLD",
    "validate_experiment_request",
    "validate_request",
    "validate_sequence_request",
]
