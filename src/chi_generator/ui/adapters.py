"""Adapters that translate GUI input into domain requests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chi_generator.domain.calculations import resolve_current
from chi_generator.domain.models import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    CurrentInputMode,
    CurrentSetpointConfig,
    ExperimentRequest,
    ExperimentSequenceRequest,
    ImpedanceConfig,
    ProcessDirection,
    ProjectConfig,
    PulseConfig,
    PulseCurrentConfig,
    RelaxationMode,
    RestPhase,
    SamplingConfig,
    SamplingMode,
    ScriptKind,
    SpacingMode,
    TimePointConfig,
    TimePointPhase,
    TimeSegmentConfig,
    VoltagePointConfig,
    VoltagePointPhase,
    VoltageWindowConfig,
)
from chi_generator.domain.service import ScriptGenerationService

from .models import (
    CurrentBasisUiMode,
    CurrentInputUiMode,
    FixedTimeUiMode,
    GuiPhaseState,
    GuiState,
    GuiValidatedPhase,
    GuiValidatedState,
    PhaseUiKind,
    RelaxationUiMode,
    VoltageInputUiMode,
    WorkspaceMode,
)
from .parsers import parse_float, parse_int
from .planning import parse_float_list


@dataclass(slots=True)
class GuiBackend:
    service: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.service, ScriptGenerationService):
            self.service = ScriptGenerationService()

    def preview(self, state: GuiState):
        validated = self._validate_state(state)
        return self.service.generate(self._build_request(validated))

    def resolve_current_preview(self, state: GuiState, phase_index: int = 0) -> tuple[float, float, float]:
        validated = self._validate_state(state)
        battery = self._build_battery(validated.draft)
        current_basis = self._build_current_basis(validated.draft)
        controlled = [phase.phase for phase in validated.phases if phase.phase.phase_kind is not PhaseUiKind.REST]
        if controlled:
            phase = controlled[min(max(phase_index, 0), len(controlled) - 1)]
            setpoint = self._build_current_setpoint(phase.current_mode, phase.rate_c, phase.current_a)
        else:
            setpoint = CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1)
        resolution = resolve_current(battery, current_basis, setpoint)
        return resolution.one_c_current_a, resolution.operating_current_a, resolution.operating_rate_c

    def _validate_state(self, state: GuiState) -> GuiValidatedState:
        return GuiValidatedState(
            draft=state,
            phases=[GuiValidatedPhase(phase=phase) for phase in state.phases],
        )

    def _build_request(self, validated: GuiValidatedState):
        if validated.draft.workspace_mode is WorkspaceMode.PULSE:
            return self._build_pulse_request(validated)
        return self._build_sequence_request(validated)

    def _build_project(self, state: GuiState) -> ProjectConfig:
        return ProjectConfig(
            scheme_name=state.scheme_name,
            file_prefix=state.file_prefix,
            export_dir=self._build_export_dir(state.export_dir),
        )

    def _build_export_dir(self, export_dir: str) -> Path:
        text = export_dir.strip()
        return Path(text) if text else Path(".")

    def _build_battery(self, state: GuiState) -> BatteryConfig:
        return BatteryConfig(
            active_material_mg=parse_float(state.active_material_mg, field_label="活性物质量"),
            theoretical_capacity_mah_mg=parse_float(state.theoretical_capacity_mah_mg, field_label="理论比容量"),
        )

    def _build_current_basis(self, state: GuiState) -> CurrentBasisConfig:
        if state.current_basis_mode is CurrentBasisUiMode.REFERENCE:
            return CurrentBasisConfig(
                mode=CurrentBasisMode.REFERENCE,
                reference_rate_c=parse_float(state.reference_rate_c, field_label="参考倍率"),
                reference_current_a=parse_float(state.reference_current_a, field_label="参考电流"),
            )
        return CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL)

    def _build_impedance_defaults(self, state: GuiState) -> ImpedanceConfig:
        return ImpedanceConfig(
            use_open_circuit_init_e=state.use_open_circuit_init_e,
            init_e_v=None if state.use_open_circuit_init_e else parse_float(state.init_e_v, field_label="初始电位"),
            high_frequency_hz=parse_float(state.high_frequency_hz, field_label="高频"),
            low_frequency_hz=parse_float(state.low_frequency_hz, field_label="低频"),
            amplitude_v=parse_float(state.amplitude_v, field_label="电压振幅"),
            quiet_time_s=parse_float(state.quiet_time_s, field_label="静置时间"),
            measurement_mode=state.impedance_measurement_mode,
        )

    def _build_sequence_request(self, validated: GuiValidatedState) -> ExperimentSequenceRequest:
        state = validated.draft
        return ExperimentSequenceRequest(
            project=self._build_project(state),
            battery=self._build_battery(state),
            current_basis=self._build_current_basis(state),
            impedance_defaults=self._build_impedance_defaults(state),
            phases=[self._build_phase(phase.phase) for phase in validated.phases],
        )

    def _build_phase(self, state: GuiPhaseState):
        if state.phase_kind is PhaseUiKind.REST:
            return RestPhase(label=state.label, duration_s=parse_float(state.rest_duration_s, field_label="静置时长"))

        payload = {
            "label": state.label,
            "direction": ProcessDirection(state.direction),
            "current_setpoint": self._build_current_setpoint(state.current_mode, state.rate_c, state.current_a),
            "voltage_window": VoltageWindowConfig(
                upper_v=parse_float(state.upper_voltage_v, field_label="上限电压"),
                lower_v=parse_float(state.lower_voltage_v, field_label="下限电压"),
            ),
            "sampling": SamplingConfig(
                pre_wait_s=parse_float(state.pre_wait_s, field_label="点前等待"),
                sample_interval_s=parse_float(state.sample_interval_s, field_label="采样间隔"),
            ),
            "insert_eis_after_each_point": state.insert_eis_after_each_point,
        }
        if state.phase_kind is PhaseUiKind.TIME_POINTS:
            payload["time_points"] = self._build_time_points(state)
            return TimePointPhase.model_validate(payload)
        payload["voltage_points"] = self._build_voltage_points(state)
        return VoltagePointPhase.model_validate(payload)

    def _build_current_setpoint(self, mode: CurrentInputUiMode, rate_text: str, current_text: str) -> CurrentSetpointConfig:
        if mode is CurrentInputUiMode.ABSOLUTE:
            return CurrentSetpointConfig(mode=CurrentInputMode.ABSOLUTE, current_a=parse_float(current_text, field_label="电流"))
        return CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=parse_float(rate_text, field_label="倍率"))

    def _build_voltage_points(self, state: GuiPhaseState) -> VoltagePointConfig:
        spacing_mode = SpacingMode.MANUAL if state.voltage_input_mode is VoltageInputUiMode.MANUAL else SpacingMode.LINEAR
        return VoltagePointConfig(
            start_v=parse_float(state.voltage_start_v, field_label="起始电压"),
            end_v=parse_float(state.voltage_end_v, field_label="结束电压"),
            step_v=parse_float(state.voltage_step_v, field_label="电压步长"),
            spacing_mode=spacing_mode,
            manual_points_v=parse_float_list(state.voltage_manual_points_text),
        )

    def _build_time_points(self, state: GuiPhaseState) -> TimePointConfig:
        manual_eis_duration_s = None
        if state.manual_eis_duration_s.strip() and float(state.manual_eis_duration_s) > 0:
            manual_eis_duration_s = parse_float(state.manual_eis_duration_s, field_label="EIS 时长覆盖")

        sampling_mode = SamplingMode(state.sampling_mode)
        segments = [
            TimeSegmentConfig(
                duration_minutes=parse_float(segment.duration_min, field_label="分段时长"),
                point_count=parse_int(segment.point_count, field_label="分段点数"),
            )
            for segment in state.segmented_points
        ]
        payload: dict[str, object] = {
            "mode": sampling_mode,
            "time_basis_mode": state.time_basis_mode,
            "manual_eis_duration_s": manual_eis_duration_s,
            "estimated_eis_duration_s": None,
        }
        if sampling_mode is SamplingMode.MANUAL:
            payload["manual_points_minutes"] = parse_float_list(state.manual_points_text)
        elif sampling_mode is SamplingMode.FIXED:
            payload["total_duration_minutes"] = parse_float(state.fixed_total_duration_min, field_label="总时长")
            if state.fixed_mode is FixedTimeUiMode.INTERVAL:
                payload["fixed_interval_minutes"] = parse_float(state.fixed_interval_min, field_label="固定间隔")
            else:
                payload["fixed_point_count"] = parse_int(state.fixed_point_count, field_label="固定点数")
        else:
            payload["segments"] = segments
        return TimePointConfig.model_validate(payload)

    def _build_pulse_request(self, validated: GuiValidatedState) -> ExperimentRequest:
        state = validated.draft
        request = ExperimentRequest(
            kind=ScriptKind.PULSE,
            project=self._build_project(state),
            battery=self._build_battery(state),
            current_basis=self._build_current_basis(state),
            discharge_current=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
            voltage_window=VoltageWindowConfig(
                upper_v=parse_float(state.pulse_upper_voltage_v, field_label="脉冲上限电压"),
                lower_v=parse_float(state.pulse_lower_voltage_v, field_label="脉冲下限电压"),
            ),
            sampling=SamplingConfig(pre_wait_s=parse_float(state.pulse_pre_wait_s, field_label="点前等待"), sample_interval_s=1.0),
            impedance=self._build_impedance_defaults(state),
        )
        relaxation_current = None
        if state.pulse_relaxation_mode is RelaxationUiMode.CONSTANT_CURRENT:
            relaxation_current = self._build_pulse_current(
                state.pulse_relaxation_current_mode,
                state.pulse_relaxation_rate_c,
                state.pulse_relaxation_current_a,
            )
        request.pulse = PulseConfig(
            relaxation_mode=RelaxationMode(state.pulse_relaxation_mode.value),
            relaxation_time_s=parse_float(state.pulse_relaxation_time_s, field_label="弛豫时间"),
            relaxation_current=relaxation_current,
            pulse_current=self._build_pulse_current(state.pulse_current_mode, state.pulse_current_rate_c, state.pulse_current_a),
            pulse_duration_s=parse_float(state.pulse_duration_s, field_label="脉冲时长"),
            pulse_count=parse_int(state.pulse_count, field_label="脉冲次数"),
            sample_interval_s=parse_float(state.pulse_sample_interval_s, field_label="脉冲采样间隔"),
            append_tail_voltage_phase=state.pulse_tail_enabled,
            tail_current=self._build_current_setpoint(state.pulse_tail_current_mode, state.pulse_tail_rate_c, state.pulse_tail_current_a),
            tail_voltage_points=VoltagePointConfig(
                start_v=3.2,
                end_v=1.5,
                step_v=0.1,
                spacing_mode=SpacingMode.MANUAL,
                manual_points_v=parse_float_list(state.pulse_tail_manual_points_text),
            ),
            tail_voltage_window=VoltageWindowConfig(
                upper_v=max(parse_float_list(state.pulse_tail_manual_points_text) or [parse_float(state.pulse_upper_voltage_v, field_label="脉冲上限电压")]),
                lower_v=min(parse_float_list(state.pulse_tail_manual_points_text) or [parse_float(state.pulse_lower_voltage_v, field_label="脉冲下限电压")]),
            ),
            tail_sample_interval_s=parse_float(state.pulse_tail_sample_interval_s, field_label="追加段采样间隔"),
            tail_insert_eis_after_each_point=state.pulse_tail_insert_eis,
        )
        return request

    def _build_pulse_current(self, mode: CurrentInputUiMode, rate_text: str, current_text: str) -> PulseCurrentConfig:
        if mode is CurrentInputUiMode.ABSOLUTE:
            return PulseCurrentConfig(mode=CurrentInputMode.ABSOLUTE, current_a=parse_float(current_text, field_label="脉冲电流"))
        return PulseCurrentConfig(mode=CurrentInputMode.RATE, rate_c=parse_float(rate_text, field_label="脉冲倍率"))


__all__ = ["GuiBackend"]
