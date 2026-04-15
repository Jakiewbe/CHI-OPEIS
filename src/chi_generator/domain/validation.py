"""Validation rules for CHI planning requests."""

from __future__ import annotations

from .calculations import IMPFT_BASELINE_S, estimate_eis_scan_duration_s, plan_time_points, plan_voltage_points, resolve_current
from .models import (
    ExperimentRequest,
    ExperimentSequenceRequest,
    RestPhase,
    RiskLevel,
    ScriptKind,
    Severity,
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
        errors.append(
            ValidationIssue(
                severity=Severity.ERROR,
                code="missing_phases",
                field="phases",
                message="At least one phase is required.",
                risk_level=RiskLevel.BLOCKING,
            )
        )
        return ValidationResult(errors=errors, warnings=warnings)

    direction_switches = 0
    previous_direction = None
    total_eis_points = 1
    total_compensation_s = 0.0
    total_rest_s = 0.0
    total_progress_s = 0.0
    total_simulated_discharge_ah = 0.0
    estimated_eis_duration_s = estimate_eis_scan_duration_s(request.impedance_defaults)
    capacity_ah = 0.0

    for index, phase in enumerate(request.phases, start=1):
        field = f"phases[{index - 1}]"
        try:
            if isinstance(phase, RestPhase):
                total_rest_s += phase.duration_s
                continue

            resolution = resolve_current(request.battery, request.current_basis, phase.current_setpoint)
            capacity_ah = max(capacity_ah, resolution.one_c_current_a)

            if previous_direction is not None and previous_direction is not phase.direction:
                direction_switches += 1
            previous_direction = phase.direction

            if isinstance(phase, TimePointPhase):
                plan = plan_time_points(
                    phase.time_points,
                    impedance=request.impedance_defaults,
                    include_interruptions=phase.insert_eis_after_each_point,
                )
                phase_progress_s = (plan.actual_points[-1] * 60.0) if plan.actual_points else 0.0
                total_progress_s += phase_progress_s
                total_compensation_s += plan.compensation_total * 60.0
                if phase.direction.value == "discharge":
                    total_simulated_discharge_ah += resolution.operating_current_a * (phase_progress_s / 3600.0)
                    if phase.insert_eis_after_each_point:
                        total_simulated_discharge_ah += resolution.operating_current_a * (len(plan.points) * estimated_eis_duration_s / 3600.0)
                if phase.insert_eis_after_each_point:
                    total_eis_points += len(plan.points)
            elif isinstance(phase, VoltagePointPhase):
                plan = plan_voltage_points(phase.voltage_points, direction=phase.direction)
                if max(plan.points) > phase.voltage_window.upper_v or min(plan.points) < phase.voltage_window.lower_v:
                    raise ValueError("voltage points must remain within the configured safety voltage window")
                if phase.insert_eis_after_each_point:
                    total_eis_points += len(plan.points)
                    if phase.direction.value == "discharge":
                        total_simulated_discharge_ah += resolution.operating_current_a * (len(plan.points) * estimated_eis_duration_s / 3600.0)
        except ValueError as exc:
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="phase_invalid",
                    field=field,
                    message=str(exc),
                    risk_level=RiskLevel.BLOCKING,
                )
            )

    if errors:
        return ValidationResult(errors=errors, warnings=warnings)

    if request.impedance_defaults.low_frequency_hz <= 0.01:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="dense_eis_low_frequency",
                field="impedance_defaults.low_frequency_hz",
                message="Dense EIS points with fl=0.01 Hz are marked high-risk by default.",
                hint=f"IMPFT simulation uses {IMPFT_BASELINE_S:.0f} s per point for capacity-risk preview.",
                risk_level=RiskLevel.HIGH,
            )
        )

    if estimated_eis_duration_s >= IMPFT_BASELINE_S:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="long_single_eis_duration",
                field="impedance_defaults.low_frequency_hz",
                message="Single-point EIS duration is long for the selected FT window.",
                hint=f"Current planning baseline is about {estimated_eis_duration_s:.0f} s per scan.",
                risk_level=RiskLevel.MEDIUM,
            )
        )

    if total_eis_points >= INTERRUPTION_WARNING_THRESHOLD:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="interrupted_progress",
                field="phases",
                message="Frequent EIS insertions will visibly interrupt the current trajectory.",
                hint="Reduce checkpoint density or only insert EIS on key checkpoints.",
                risk_level=RiskLevel.HIGH,
            )
        )

    if any(
        isinstance(phase, VoltagePointPhase)
        and phase.direction.value == "charge"
        and phase.insert_eis_after_each_point
        for phase in request.phases
    ):
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="charge_cp_peis_transition",
                field="phases",
                message="Charge voltage checkpoints switch directly from CP into PEIS at the target voltage.",
                hint="The generator renders charge CP with eh=target and el=lower safety limit; treat lower_v as the safety floor and keep target points ascending.",
                risk_level=RiskLevel.HIGH,
            )
        )

    if total_compensation_s >= 600:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="high_compensation_total",
                field="phases",
                message="Interruption compensation adds substantial extra time to later current holds.",
                hint=f"Estimated accumulated compensation is about {total_compensation_s / 60.0:.1f} min.",
                risk_level=RiskLevel.HIGH,
            )
        )

    if any(
        isinstance(phase, TimePointPhase) and phase.time_points.time_basis_mode.value == "capacity_compensated"
        for phase in request.phases
    ):
        warnings.append(
            ValidationIssue(
                severity=Severity.INFO,
                code="ctc_enabled",
                field="phases",
                message="CTC capacity compensation is enabled; current-hold durations are reduced to offset IMPFT capacity consumption.",
                risk_level=RiskLevel.LOW,
            )
        )

    if direction_switches >= FREQUENT_DIRECTION_SWITCH_THRESHOLD:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="frequent_direction_switches",
                field="phases",
                message="Phase direction switches are frequent; confirm this matches the intended protocol.",
                risk_level=RiskLevel.MEDIUM,
            )
        )

    if total_rest_s > total_progress_s and total_rest_s > 0:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="rest_dominates_sequence",
                field="phases",
                message="Total rest time exceeds electrochemical work time; confirm this is intentional.",
                risk_level=RiskLevel.MEDIUM,
            )
        )

    if capacity_ah > 0 and total_simulated_discharge_ah >= capacity_ah:
        warnings.append(
            ValidationIssue(
                severity=Severity.WARNING,
                code="soc_depletion_risk",
                field="phases",
                message="Simulated SoC reaches 0% before all EIS checkpoints complete.",
                hint="Dashboard red markers indicate checkpoints predicted to be lost.",
                risk_level=RiskLevel.HIGH,
            )
        )

    return ValidationResult(errors=errors, warnings=warnings)


def validate_request(request: ExperimentRequest) -> ValidationResult:
    if request.kind is ScriptKind.PULSE:
        errors: list[ValidationIssue] = []
        if request.pulse is None:
            errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="missing_pulse",
                    field="pulse",
                    message="Pulse mode requires pulse configuration.",
                    risk_level=RiskLevel.BLOCKING,
                )
            )
        return ValidationResult(errors=errors, warnings=[])
    return ValidationResult()


__all__ = [
    "FREQUENT_DIRECTION_SWITCH_THRESHOLD",
    "INTERRUPTION_WARNING_THRESHOLD",
    "validate_request",
    "validate_sequence_request",
]
