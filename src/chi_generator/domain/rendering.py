"""Macro command rendering helpers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
import re

from .calculations import (
    apply_direction,
    estimate_capacity_loss_mah,
    estimate_eis_scan_duration_s,
    plan_dod_points,
    plan_time_points,
    plan_voltage_points,
    resolve_current,
    resolve_sequence_capacity_ah,
    resolve_pulse_current,
    simulate_soc_trace,
)
from .models import (
    ExperimentRequest,
    ExperimentSequenceRequest,
    DodPointPhase,
    EisInitStrategy,
    ImpedanceConfig,
    ImpedanceMeasurementMode,
    PhaseKind,
    PhaseRenderPlan,
    PulseConfig,
    RelaxationMode,
    RestPhase,
    SamplingMode,
    TimePointPhase,
    ValidationIssue,
    VoltagePointConfig,
    VoltagePointPhase,
)


def format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-12:
        return str(int(round(value)))
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def voltage_tag(voltage_v: float) -> str:
    text = f"{voltage_v:.2f}".replace("-", "m").replace(".", "p")
    return f"{text}V"


def time_tag(time_minute: float) -> str:
    return f"T{format_number(time_minute).replace('.', '_')}M"


def dod_tag(dod_percent: float) -> str:
    return f"DOD{format_number(dod_percent).replace('.', '_')}P"


def render_block(lines: Iterable[str]) -> str:
    return "\n".join(lines).strip()


def render_comment_line(text: str) -> str:
    return f"# {text}"


def render_issues(issues: list[ValidationIssue]) -> str:
    if not issues:
        return ""
    blocks: list[str] = []
    for issue in issues:
        prefix = issue.severity.value.upper()
        field_text = f" [{issue.field}]" if issue.field else ""
        blocks.append(f"{prefix}{field_text}: {issue.message}")
        if issue.hint:
            blocks.append(f"hint: {issue.hint}")
    return "\n".join(blocks)


def wrap_commented_script(*, summary_lines: list[str], script_lines: list[str], issues: list[ValidationIssue]) -> str:
    output: list[str] = []
    output.extend(render_comment_line(line) for line in summary_lines)
    if issues:
        output.append(render_comment_line("Validation"))
        output.extend(render_comment_line(line) for line in render_issues(issues).splitlines())
    output.extend(script_lines)
    return render_block(output)


class SaveNameAllocator:
    """Allocate unique save names within a single script generation session.

    Since the generated script uses ``fileoverride`` (CHI overwrites existing
    files on disk), we no longer scan the export directory for occupied names.
    We only ensure uniqueness within the current script to avoid self-collisions.
    """

    def __init__(self, export_dir: Path) -> None:
        del export_dir  # kept for backward-compatible signature
        self._used: set[str] = set()
        self._next_by_base: Counter[str] = Counter()

    def allocate(self, preferred: str) -> str:
        base = sanitize_save_token(preferred)
        key = chi_save_key(base)

        if key not in self._next_by_base and key not in self._used:
            self._used.add(key)
            self._next_by_base[key] = 2
            return base

        index = self._next_by_base[key] or 2
        candidate = f"{base}_{index:03d}"
        while chi_save_key(candidate) in self._used:
            index += 1
            candidate = f"{base}_{index:03d}"
        self._used.add(chi_save_key(candidate))
        self._next_by_base[key] = index + 1
        return candidate


def _folder_text(export_dir: Path) -> str:
    return str(export_dir).replace("/", "\\")


def sanitize_save_token(value: str) -> str:
    """Keep generated save names within CHI's simple filename rules."""

    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
    return clean or "CHI"


def chi_save_key(value: str) -> str:
    """Return the filename stem CHI uses before an extension separator."""

    return value.split(".", 1)[0].lower()


def _save_name(prefix: str, family: str, suffix: str) -> str:
    clean = sanitize_save_token(prefix)
    return f"{clean}_{family}_{suffix}"


def _phase_token(index: int) -> str:
    return f"S{index:02d}"


def _render_common_header(export_dir: Path) -> list[str]:
    return ["fileoverride", f"folder={_folder_text(export_dir)}", "cellon"]


def _render_common_footer() -> list[str]:
    return ["celloff", "end"]


def _render_delay(duration_s: float) -> list[str]:
    if duration_s <= 0:
        return []
    return [f"delay={format_number(duration_s)}"]


def _render_impedance(
    impedance: ImpedanceConfig,
    *,
    save_name: str,
    init_strategy: EisInitStrategy | None = None,
    init_e_v: float | None = None,
) -> list[str]:
    strategy = init_strategy
    if strategy is None:
        strategy = EisInitStrategy.OPEN_CIRCUIT if impedance.use_open_circuit_init_e else EisInitStrategy.MANUAL
        if strategy is EisInitStrategy.MANUAL:
            init_e_v = impedance.init_e_v

    if strategy is EisInitStrategy.OPEN_CIRCUIT:
        init_line = "eio"
    else:
        if init_e_v is None:
            raise ValueError("explicit EIS initial voltage is required")
        init_line = f"ei={format_number(init_e_v)}"
    lines = [
        "tech=imp",
        init_line,
        f"fh={format_number(impedance.high_frequency_hz)}",
        f"fl={format_number(impedance.low_frequency_hz)}",
        f"amp={format_number(impedance.amplitude_v)}",
        f"qt={format_number(impedance.quiet_time_s)}",
    ]
    if impedance.auto_sens:
        lines.append("impautosens")
    lines.append("impft" if impedance.measurement_mode is ImpedanceMeasurementMode.FT else "impsf")
    lines.extend(["run", f"save={save_name}"])
    return lines


def _render_istep(
    *,
    current_a: float,
    duration_s: float,
    high_v: float,
    low_v: float,
    sample_interval_s: float,
    save_name: str,
) -> list[str]:
    return [
        "tech=istep",
        f"is1={format_number(current_a)}",
        f"st1={format_number(duration_s)}",
        f"eh={format_number(high_v)}",
        f"el={format_number(low_v)}",
        f"si={format_number(sample_interval_s)}",
        "cl=1",
        "run",
        f"save={save_name}",
    ]


def _render_cp(
    *,
    current_a: float,
    target_v: float,
    high_v: float,
    low_v: float,
    sample_interval_s: float,
    save_name: str,
) -> list[str]:
    if current_a < 0:
        upper_v = target_v
        lower_v = low_v
    else:
        upper_v = high_v
        lower_v = target_v

    return [
        "tech=cp",
        f"ic={format_number(current_a)}",
        "ia=0",
        f"eh={format_number(upper_v)}",
        f"el={format_number(lower_v)}",
        "tc=100000",
        "ta=0.05",
        "pn=n",
        f"si={format_number(sample_interval_s)}",
        "cl=1",
        "prioe",
        "run",
        f"save={save_name}",
    ]


def _voltage_phase_impedance_kwargs(phase: VoltagePointPhase, target_v: float) -> dict[str, EisInitStrategy | float]:
    if phase.eis_init_strategy is EisInitStrategy.TARGET_VOLTAGE:
        return {"init_strategy": EisInitStrategy.TARGET_VOLTAGE, "init_e_v": target_v}
    if phase.eis_init_strategy is EisInitStrategy.OPEN_CIRCUIT:
        return {"init_strategy": EisInitStrategy.OPEN_CIRCUIT}
    if phase.manual_init_e_v is None:
        raise ValueError("manual EIS initial voltage is required")
    return {"init_strategy": EisInitStrategy.MANUAL, "init_e_v": phase.manual_init_e_v}


def render_sequence_request(request: ExperimentSequenceRequest) -> tuple[list[str], dict[str, object]]:
    prefix = request.project.file_prefix
    minimal: list[str] = []
    phase_plans: list[PhaseRenderPlan] = []
    simulation_steps: list[tuple[float, float]] = []
    eis_duration_s = estimate_eis_scan_duration_s(request.impedance_defaults)
    allocator = SaveNameAllocator(request.project.export_dir)
    known_wall_clock_s = 0.0
    absolute_cursor_s: float | None = 0.0
    simulation_active = True
    soc_prediction_complete = True

    def append_block(lines: list[str]) -> None:
        if minimal:
            minimal.append("")
        minimal.extend(lines)

    def append_simulation(duration_s: float, current_a: float) -> None:
        if simulation_active:
            simulation_steps.append((duration_s, current_a))

    append_block(_render_common_header(request.project.export_dir))
    append_block(
        _render_impedance(
            request.impedance_defaults,
            save_name=allocator.allocate(_save_name(prefix, "EIS", "OCV")),
        )
    )
    known_wall_clock_s += eis_duration_s
    absolute_cursor_s = known_wall_clock_s
    append_simulation(eis_duration_s, 0.0)

    one_c_current_a = None
    for phase_index, phase in enumerate(request.phases, start=1):
        phase_start_s = absolute_cursor_s

        if isinstance(phase, RestPhase):
            append_block(_render_delay(phase.duration_s))
            known_wall_clock_s += phase.duration_s
            append_simulation(phase.duration_s, 0.0)
            if absolute_cursor_s is not None:
                absolute_cursor_s += phase.duration_s
            phase_plans.append(
                PhaseRenderPlan(
                    phase_index=phase_index,
                    label=phase.label,
                    phase_kind=PhaseKind.REST,
                    wall_clock_total_s=phase.duration_s,
                    known_wall_clock_s=phase.duration_s,
                    start_time_s=phase_start_s,
                    end_time_s=absolute_cursor_s,
                    timing_complete=phase_start_s is not None,
                )
            )
            continue

        resolution = resolve_current(request.battery, request.current_basis, phase.current_setpoint)
        one_c_current_a = one_c_current_a or resolution.one_c_current_a
        signed_current_a = apply_direction(resolution.operating_current_a, phase.direction)

        if isinstance(phase, TimePointPhase):
            point_plan = plan_time_points(
                phase.time_points,
                impedance=request.impedance_defaults,
                include_interruptions=phase.insert_eis_after_each_point,
            )
            point_count = len(point_plan.points)
            eis_count = point_count if phase.insert_eis_after_each_point else 0
            phase_elapsed_s = 0.0
            marker_times: list[float] = []

            for effective_point, delta_min in zip(point_plan.points, point_plan.deltas, strict=True):
                if phase.sampling.pre_wait_s > 0:
                    append_block(_render_delay(phase.sampling.pre_wait_s))
                    phase_elapsed_s += phase.sampling.pre_wait_s
                    append_simulation(phase.sampling.pre_wait_s, 0.0)
                tag = time_tag(effective_point)
                step_duration_s = delta_min * 60.0
                append_block(
                    _render_istep(
                        current_a=signed_current_a,
                        duration_s=step_duration_s,
                        high_v=phase.voltage_window.upper_v,
                        low_v=phase.voltage_window.lower_v,
                        sample_interval_s=phase.sampling.sample_interval_s,
                        save_name=allocator.allocate(_save_name(prefix, f"{_phase_token(phase_index)}_CC", tag)),
                    )
                )
                phase_elapsed_s += step_duration_s
                append_simulation(step_duration_s, signed_current_a)
                if phase.insert_eis_after_each_point:
                    if phase_start_s is not None:
                        marker_times.append(phase_start_s + phase_elapsed_s)
                    append_block(
                        _render_impedance(
                            request.impedance_defaults,
                            save_name=allocator.allocate(_save_name(prefix, f"{_phase_token(phase_index)}_EIS", tag)),
                        )
                    )
                    phase_elapsed_s += point_plan.eis_duration_s
                    append_simulation(point_plan.eis_duration_s, 0.0)

            known_wall_clock_s += phase_elapsed_s
            if absolute_cursor_s is not None:
                absolute_cursor_s += phase_elapsed_s
            phase_plans.append(
                PhaseRenderPlan(
                    phase_index=phase_index,
                    label=phase.label,
                    phase_kind=PhaseKind.TIME_POINTS,
                    direction=phase.direction,
                    sampling_mode=phase.time_points.mode,
                    effective_points=point_plan.points,
                    rendered_points=point_plan.actual_points,
                    deltas_s=[delta * 60.0 for delta in point_plan.deltas],
                    compensation_offsets_min=point_plan.compensation_offsets,
                    eis_marker_times_s=marker_times,
                    point_count=point_count,
                    eis_count=eis_count,
                    wall_clock_total_s=phase_elapsed_s,
                    known_wall_clock_s=phase_elapsed_s,
                    start_time_s=phase_start_s,
                    end_time_s=absolute_cursor_s,
                    timing_complete=phase_start_s is not None,
                    operating_current_a=signed_current_a,
                    eis_duration_s=point_plan.eis_duration_s,
                    insert_eis_after_each_point=phase.insert_eis_after_each_point,
                    time_basis_mode=phase.time_points.time_basis_mode,
                )
            )
            continue

        if isinstance(phase, DodPointPhase):
            point_plan = plan_dod_points(phase.dod_points, battery=request.battery, current_a=resolution.operating_current_a)
            point_count = len(point_plan.points)
            eis_count = point_count if phase.insert_eis_after_each_point else 0
            phase_elapsed_s = 0.0
            marker_times: list[float] = []

            for dod_percent, delta_min in zip(point_plan.points, point_plan.deltas, strict=True):
                if phase.sampling.pre_wait_s > 0:
                    append_block(_render_delay(phase.sampling.pre_wait_s))
                    phase_elapsed_s += phase.sampling.pre_wait_s
                    append_simulation(phase.sampling.pre_wait_s, 0.0)
                tag = dod_tag(dod_percent)
                step_duration_s = delta_min * 60.0
                append_block(
                    _render_istep(
                        current_a=signed_current_a,
                        duration_s=step_duration_s,
                        high_v=phase.voltage_window.upper_v,
                        low_v=phase.voltage_window.lower_v,
                        sample_interval_s=phase.sampling.sample_interval_s,
                        save_name=allocator.allocate(_save_name(prefix, f"{_phase_token(phase_index)}_CC", tag)),
                    )
                )
                phase_elapsed_s += step_duration_s
                append_simulation(step_duration_s, signed_current_a)
                if phase.insert_eis_after_each_point:
                    if phase.post_trigger_rest_s > 0:
                        append_block(_render_delay(phase.post_trigger_rest_s))
                        phase_elapsed_s += phase.post_trigger_rest_s
                        append_simulation(phase.post_trigger_rest_s, 0.0)
                    if phase_start_s is not None:
                        marker_times.append(phase_start_s + phase_elapsed_s)
                    append_block(
                        _render_impedance(
                            request.impedance_defaults,
                            save_name=allocator.allocate(_save_name(prefix, f"{_phase_token(phase_index)}_EIS", tag)),
                            init_strategy=EisInitStrategy.OPEN_CIRCUIT,
                        )
                    )
                    phase_elapsed_s += eis_duration_s
                    append_simulation(eis_duration_s, 0.0)

            known_wall_clock_s += phase_elapsed_s
            if absolute_cursor_s is not None:
                absolute_cursor_s += phase_elapsed_s
            phase_plans.append(
                PhaseRenderPlan(
                    phase_index=phase_index,
                    label=phase.label,
                    phase_kind=PhaseKind.DOD_POINTS,
                    direction=phase.direction,
                    sampling_mode=phase.dod_points.capacity_basis,
                    effective_points=point_plan.points,
                    rendered_points=point_plan.actual_points,
                    deltas_s=[delta * 60.0 for delta in point_plan.deltas],
                    eis_marker_times_s=marker_times,
                    point_count=point_count,
                    eis_count=eis_count,
                    wall_clock_total_s=phase_elapsed_s,
                    known_wall_clock_s=phase_elapsed_s,
                    start_time_s=phase_start_s,
                    end_time_s=absolute_cursor_s,
                    timing_complete=phase_start_s is not None,
                    operating_current_a=signed_current_a,
                    eis_duration_s=eis_duration_s if phase.insert_eis_after_each_point else 0.0,
                    insert_eis_after_each_point=phase.insert_eis_after_each_point,
                )
            )
            continue

        point_plan = plan_voltage_points(phase.voltage_points, direction=phase.direction)
        point_count = len(point_plan.points)
        eis_count = point_count if phase.insert_eis_after_each_point else 0
        phase_known_s = 0.0
        phase_eis_duration_s = eis_duration_s if phase.insert_eis_after_each_point else 0.0

        for target_v in point_plan.points:
            if phase.sampling.pre_wait_s > 0:
                append_block(_render_delay(phase.sampling.pre_wait_s))
                phase_known_s += phase.sampling.pre_wait_s
                append_simulation(phase.sampling.pre_wait_s, 0.0)
            tag = voltage_tag(target_v)
            append_block(
                _render_cp(
                    current_a=signed_current_a,
                    target_v=target_v,
                    high_v=phase.voltage_window.upper_v,
                    low_v=phase.voltage_window.lower_v,
                    sample_interval_s=phase.sampling.sample_interval_s,
                    save_name=allocator.allocate(_save_name(prefix, f"{_phase_token(phase_index)}_CC", tag)),
                )
            )
            simulation_active = False
            soc_prediction_complete = False
            absolute_cursor_s = None
            if phase.insert_eis_after_each_point:
                if phase.post_trigger_rest_s > 0:
                    append_block(_render_delay(phase.post_trigger_rest_s))
                    phase_known_s += phase.post_trigger_rest_s
                    append_simulation(phase.post_trigger_rest_s, 0.0)
                append_block(
                    _render_impedance(
                        request.impedance_defaults,
                        save_name=allocator.allocate(_save_name(prefix, f"{_phase_token(phase_index)}_EIS", tag)),
                        **_voltage_phase_impedance_kwargs(phase, target_v),
                    )
                )
                phase_known_s += eis_duration_s
                append_simulation(eis_duration_s, 0.0)

        known_wall_clock_s += phase_known_s
        phase_plans.append(
            PhaseRenderPlan(
                phase_index=phase_index,
                label=phase.label,
                phase_kind=PhaseKind.VOLTAGE_POINTS,
                direction=phase.direction,
                sampling_mode=phase.voltage_points.spacing_mode,
                effective_points=point_plan.points,
                rendered_points=point_plan.actual_points,
                point_count=point_count,
                eis_count=eis_count,
                wall_clock_total_s=None,
                known_wall_clock_s=phase_known_s,
                start_time_s=phase_start_s,
                end_time_s=None,
                timing_complete=False,
                operating_current_a=signed_current_a,
                eis_duration_s=phase_eis_duration_s,
                insert_eis_after_each_point=phase.insert_eis_after_each_point,
            )
        )

    append_block(_render_common_footer())

    capacity_ah = resolve_sequence_capacity_ah(request)
    soc_trace, soc_zero_time_s = simulate_soc_trace(capacity_ah=capacity_ah, steps=simulation_steps)
    lost_checkpoint_count = 0
    for plan in phase_plans:
        lost_markers = [marker for marker in plan.eis_marker_times_s if soc_zero_time_s is not None and marker >= soc_zero_time_s]
        plan.lost_eis_marker_times_s = lost_markers
        lost_checkpoint_count += len(lost_markers)

    total_eis = 1 + sum(plan.eis_count for plan in phase_plans)
    total_capacity_ah = capacity_ah
    summary = {
        "one_c_current_a": one_c_current_a,
        "estimated_eis_duration_s": eis_duration_s,
        "phase_plans": phase_plans,
        "phase_count": len(phase_plans),
        "total_wall_clock_s": known_wall_clock_s if absolute_cursor_s is not None else None,
        "known_wall_clock_s": known_wall_clock_s,
        "soc_prediction_complete": soc_prediction_complete,
        "total_point_count": sum(plan.point_count for plan in phase_plans),
        "total_eis_count": total_eis,
        "total_interruption_equivalent_mah": (total_eis * estimate_capacity_loss_mah(one_c_current_a or 0.0, eis_duration_s)) if one_c_current_a else 0.0,
        "total_capacity_ah": total_capacity_ah,
        "soc_trace": soc_trace,
        "soc_zero_time_s": soc_zero_time_s,
        "lost_checkpoint_count": lost_checkpoint_count,
    }
    return minimal, summary


def render_pulse_request(request: ExperimentRequest) -> tuple[list[str], dict[str, object]]:
    pulse: PulseConfig = request.pulse
    prefix = request.project.file_prefix
    minimal: list[str] = []
    allocator = SaveNameAllocator(request.project.export_dir)

    def append_block(lines: list[str]) -> None:
        if minimal:
            minimal.append("")
        minimal.extend(lines)

    append_block(_render_common_header(request.project.export_dir))
    append_block(
        _render_impedance(
            request.impedance,
            save_name=allocator.allocate(_save_name(prefix, "EIS", "OCV")),
        )
    )
    for index in range(1, pulse.pulse_count + 1):
        append_block(_render_delay(request.sampling.pre_wait_s))
        
        relaxation_current_a = 0.0
        if pulse.relaxation_mode is RelaxationMode.CONSTANT_CURRENT:
            relaxation_current_a, _ = resolve_pulse_current(request.battery, request.current_basis, pulse.relaxation_current)
        if pulse.relaxation_mode is RelaxationMode.REST:
            append_block(_render_delay(pulse.relaxation_time_s))
        else:
            append_block(
                _render_istep(
                    current_a=relaxation_current_a,
                    duration_s=pulse.relaxation_time_s,
                    high_v=request.voltage_window.upper_v,
                    low_v=request.voltage_window.lower_v,
                    sample_interval_s=pulse.sample_interval_s,
                    save_name=allocator.allocate(_save_name(prefix, "REL", f"{index:02d}")),
                )
            )
        append_block(
            _render_impedance(
                request.impedance,
                save_name=allocator.allocate(_save_name(prefix, "EIS", f"PRE{index:02d}")),
            )
        )

        pulse_current_a, _ = resolve_pulse_current(request.battery, request.current_basis, pulse.pulse_current)
        append_block(
            _render_istep(
                current_a=pulse_current_a,
                duration_s=pulse.pulse_duration_s,
                high_v=request.voltage_window.upper_v,
                low_v=request.voltage_window.lower_v,
                sample_interval_s=pulse.sample_interval_s,
                save_name=allocator.allocate(_save_name(prefix, "PULSE", f"{index:02d}")),
            )
        )
        append_block(
            _render_impedance(
                request.impedance,
                save_name=allocator.allocate(_save_name(prefix, "EIS", f"POST{index:02d}")),
            )
        )
    if pulse.append_tail_voltage_phase:
        tail_current_a = apply_direction(resolve_current(request.battery, request.current_basis, pulse.tail_current).operating_current_a, request.direction)
        tail_plan = plan_voltage_points(pulse.tail_voltage_points, direction=request.direction)
        for target_v in tail_plan.points:
            tag = voltage_tag(target_v)
            append_block(
                _render_cp(
                    current_a=tail_current_a,
                    target_v=target_v,
                    high_v=pulse.tail_voltage_window.upper_v,
                    low_v=pulse.tail_voltage_window.lower_v,
                    sample_interval_s=pulse.tail_sample_interval_s,
                    save_name=allocator.allocate(_save_name(prefix, "TAIL_CC", tag)),
                )
            )
            if pulse.tail_insert_eis_after_each_point:
                append_block(
                    _render_impedance(
                        request.impedance,
                        save_name=allocator.allocate(_save_name(prefix, "TAIL_EIS", tag)),
                        init_strategy=EisInitStrategy.TARGET_VOLTAGE,
                        init_e_v=target_v,
                    )
                )
    append_block(_render_common_footer())
    one_c_current = resolve_current(request.battery, request.current_basis, request.discharge_current).one_c_current_a
    return minimal, {
        "one_c_current_a": one_c_current,
        "pulse_count": pulse.pulse_count,
        "estimated_eis_duration_s": estimate_eis_scan_duration_s(request.impedance),
    }
__all__ = [
    "format_number",
    "dod_tag",
    "render_block",
    "render_comment_line",
    "render_issues",
    "render_pulse_request",
    "render_sequence_request",
    "time_tag",
    "voltage_tag",
    "wrap_commented_script",
]
