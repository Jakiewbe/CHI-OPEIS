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
    ScriptKind,
    TimeBasisMode,
    TimePointConfig,
    TimePointPhase,
    TimeSegmentConfig,
    VoltagePointConfig,
    VoltagePointPhase,
    VoltageWindowConfig,
)
from chi_generator.domain.service import ScriptGenerationService

from .models import CurrentInputUiMode, GuiPhaseState, GuiState, PhaseUiKind, RelaxationUiMode, WorkspaceMode
from .parsers import parse_float, parse_int


@dataclass(slots=True)
class GuiBackend:
    service: object | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.service, ScriptGenerationService):
            self.service = ScriptGenerationService()

    def preview(self, state: GuiState):
        return self.service.generate(self._build_request(state))

    def resolve_current_preview(self, state: GuiState, phase_index: int = 0) -> tuple[float, float, float]:
        battery = BatteryConfig(
            active_material_mg=parse_float(state.active_material_mg, field_label="active material mass"),
            theoretical_capacity_mah_mg=parse_float(state.theoretical_capacity_mah_mg, field_label="theoretical specific capacity"),
        )
        current_basis = CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL)
        controlled = [phase for phase in state.phases if phase.phase_kind is not PhaseUiKind.REST]
        if controlled:
            phase = controlled[min(max(phase_index, 0), len(controlled) - 1)]
            setpoint = self._build_current_setpoint(phase.current_mode, phase.rate_c, phase.current_a)
        else:
            setpoint = CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1)
        resolution = resolve_current(battery, current_basis, setpoint)
        return resolution.one_c_current_a, resolution.operating_current_a, resolution.operating_rate_c

    def _build_request(self, state: GuiState):
        if state.workspace_mode is WorkspaceMode.PULSE:
            return self._build_pulse_request(state)
        return self._build_sequence_request(state)

    def _build_sequence_request(self, state: GuiState) -> ExperimentSequenceRequest:
        return ExperimentSequenceRequest(
            project=ProjectConfig(
                scheme_name=state.scheme_name,
                file_prefix=state.file_prefix,
                export_dir=Path(state.export_dir or ".").resolve(),
            ),
            battery=BatteryConfig(
                active_material_mg=parse_float(state.active_material_mg, field_label="active material mass"),
                theoretical_capacity_mah_mg=parse_float(state.theoretical_capacity_mah_mg, field_label="theoretical specific capacity"),
            ),
            current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
            impedance_defaults=ImpedanceConfig(
                use_open_circuit_init_e=state.use_open_circuit_init_e,
                init_e_v=None if state.use_open_circuit_init_e else parse_float(state.init_e_v, field_label="Init E"),
                high_frequency_hz=parse_float(state.high_frequency_hz, field_label="fh"),
                low_frequency_hz=parse_float(state.low_frequency_hz, field_label="fl"),
                amplitude_v=parse_float(state.amplitude_v, field_label="amplitude"),
                quiet_time_s=parse_float(state.quiet_time_s, field_label="quiet time"),
            ),
            phases=[self._build_phase(phase_state) for phase_state in state.phases],
        )

    def _build_phase(self, state: GuiPhaseState):
        if state.phase_kind is PhaseUiKind.REST:
            return RestPhase(label=state.label, duration_s=parse_float(state.rest_duration_s, field_label="rest duration"))

        payload = {
            "label": state.label,
            "direction": ProcessDirection(state.direction),
            "current_setpoint": self._build_current_setpoint(state.current_mode, state.rate_c, state.current_a),
            "voltage_window": VoltageWindowConfig(
                upper_v=parse_float(state.upper_voltage_v, field_label="upper voltage"),
                lower_v=parse_float(state.lower_voltage_v, field_label="lower voltage"),
            ),
            "sampling": SamplingConfig(
                pre_wait_s=parse_float(state.pre_wait_s, field_label="pre-wait"),
                sample_interval_s=parse_float(state.sample_interval_s, field_label="sample interval"),
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
            return CurrentSetpointConfig(mode=CurrentInputMode.ABSOLUTE, current_a=parse_float(current_text, field_label="current"))
        return CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=parse_float(rate_text, field_label="rate"))

    def _build_voltage_points(self, state: GuiPhaseState) -> VoltagePointConfig:
        return VoltagePointConfig(
            start_v=parse_float(state.voltage_start_v, field_label="voltage start"),
            end_v=parse_float(state.voltage_end_v, field_label="voltage end"),
            step_v=parse_float(state.voltage_step_v, field_label="voltage step"),
        )

    def _build_time_points(self, state: GuiPhaseState) -> TimePointConfig:
        time_basis_mode = TimeBasisMode(state.time_basis_mode)
        manual_eis_duration_s = None
        if time_basis_mode is TimeBasisMode.INTERRUPTION_COMPENSATED:
            manual_eis_duration_s = parse_float(state.manual_eis_duration_s, field_label="manual EIS duration")
        return TimePointConfig(
            early=TimeSegmentConfig(
                duration_minutes=parse_float(state.early_duration_min, field_label="early duration"),
                point_count=parse_int(state.early_point_count, field_label="early point count"),
            ),
            plateau=TimeSegmentConfig(
                duration_minutes=parse_float(state.plateau_duration_min, field_label="plateau duration"),
                point_count=parse_int(state.plateau_point_count, field_label="plateau point count"),
            ),
            late=TimeSegmentConfig(
                duration_minutes=parse_float(state.late_duration_min, field_label="late duration"),
                point_count=parse_int(state.late_point_count, field_label="late point count"),
            ),
            time_basis_mode=time_basis_mode,
            manual_eis_duration_s=manual_eis_duration_s,
        )

    def _build_pulse_request(self, state: GuiState) -> ExperimentRequest:
        request = ExperimentRequest(
            kind=ScriptKind.PULSE,
            project=ProjectConfig(
                scheme_name=state.scheme_name,
                file_prefix=state.file_prefix,
                export_dir=Path(state.export_dir or ".").resolve(),
            ),
            battery=BatteryConfig(
                active_material_mg=parse_float(state.active_material_mg, field_label="active material mass"),
                theoretical_capacity_mah_mg=parse_float(state.theoretical_capacity_mah_mg, field_label="theoretical specific capacity"),
            ),
            current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
            discharge_current=CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
            voltage_window=VoltageWindowConfig(
                upper_v=parse_float(state.pulse_upper_voltage_v, field_label="pulse upper voltage"),
                lower_v=parse_float(state.pulse_lower_voltage_v, field_label="pulse lower voltage"),
            ),
            sampling=SamplingConfig(pre_wait_s=parse_float(state.pulse_pre_wait_s, field_label="pulse pre-wait"), sample_interval_s=0.001),
            impedance=ImpedanceConfig(
                use_open_circuit_init_e=state.use_open_circuit_init_e,
                init_e_v=None if state.use_open_circuit_init_e else parse_float(state.init_e_v, field_label="Init E"),
                high_frequency_hz=parse_float(state.high_frequency_hz, field_label="fh"),
                low_frequency_hz=parse_float(state.low_frequency_hz, field_label="fl"),
                amplitude_v=parse_float(state.amplitude_v, field_label="amplitude"),
                quiet_time_s=parse_float(state.quiet_time_s, field_label="quiet time"),
            ),
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
            relaxation_time_s=parse_float(state.pulse_relaxation_time_s, field_label="relaxation time"),
            relaxation_current=relaxation_current,
            pulse_current=self._build_pulse_current(state.pulse_current_mode, state.pulse_current_rate_c, state.pulse_current_a),
            pulse_duration_s=parse_float(state.pulse_duration_s, field_label="pulse duration"),
            pulse_count=parse_int(state.pulse_count, field_label="pulse count"),
            sample_interval_s=parse_float(state.pulse_sample_interval_s, field_label="pulse sample interval"),
        )
        return request

    def _build_pulse_current(self, mode: CurrentInputUiMode, rate_text: str, current_text: str) -> PulseCurrentConfig:
        if mode is CurrentInputUiMode.ABSOLUTE:
            return PulseCurrentConfig(mode=CurrentInputMode.ABSOLUTE, current_a=parse_float(current_text, field_label="pulse current"))
        return PulseCurrentConfig(mode=CurrentInputMode.RATE, rate_c=parse_float(rate_text, field_label="pulse rate"))


__all__ = ["GuiBackend"]
