"""Typed domain models for the CHI in-situ EIS generator."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PositiveFloat = Annotated[float, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0)]
PotentialFloat = Annotated[float, Field(ge=-10, le=10)]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, use_enum_values=False)


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


IssueSeverity = Severity


class ScriptVariant(StrEnum):
    COMMENTED = "commented"
    MINIMAL = "minimal"


class ScriptKind(StrEnum):
    SEQUENCE = "sequence"
    PULSE = "pulse"
    FIXED_VOLTAGE = "fixed_voltage"
    TIME_POINTS = "time_points"
    ACTIVATION_MAIN = "activation_main"


class ProcessDirection(StrEnum):
    DISCHARGE = "discharge"
    CHARGE = "charge"


class TimeBasisMode(StrEnum):
    ACTIVE_PROGRESS = "active_progress"
    INTERRUPTION_COMPENSATED = "interruption_compensated"


class PlanningStrategy(StrEnum):
    LEGACY_DEFAULT = "legacy_default"
    INTERRUPTION_AWARE = "interruption_aware"


class PhaseKind(StrEnum):
    TIME_POINTS = "time_points"
    VOLTAGE_POINTS = "voltage_points"
    REST = "rest"


class ProjectConfig(DomainModel):
    scheme_name: str = Field(min_length=1)
    file_prefix: str = Field(min_length=1)
    export_dir: Path


class BatteryConfig(DomainModel):
    active_material_mg: PositiveFloat
    theoretical_capacity_mah_mg: PositiveFloat


class CurrentBasisMode(StrEnum):
    MATERIAL = "material"
    REFERENCE = "reference"


class CurrentInputMode(StrEnum):
    RATE = "rate"
    ABSOLUTE = "absolute"


class CurrentBasisConfig(DomainModel):
    mode: CurrentBasisMode = CurrentBasisMode.MATERIAL
    reference_rate_c: PositiveFloat | None = None
    reference_current_a: PositiveFloat | None = None

    @model_validator(mode="after")
    def _validate_reference(self) -> "CurrentBasisConfig":
        if self.mode is CurrentBasisMode.REFERENCE:
            if self.reference_rate_c is None or self.reference_current_a is None:
                raise ValueError("reference mode requires reference_rate_c and reference_current_a")
        return self


class CurrentSetpointConfig(DomainModel):
    mode: CurrentInputMode = CurrentInputMode.RATE
    rate_c: PositiveFloat | None = Field(default=0.1)
    current_a: PositiveFloat | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "CurrentSetpointConfig":
        if self.mode is CurrentInputMode.RATE and self.rate_c is None:
            raise ValueError("rate mode requires rate_c")
        if self.mode is CurrentInputMode.ABSOLUTE and self.current_a is None:
            raise ValueError("absolute mode requires current_a")
        return self


class VoltageWindowConfig(DomainModel):
    upper_v: PositiveFloat = 3.2
    lower_v: PotentialFloat = 1.5

    @model_validator(mode="after")
    def _validate_window(self) -> "VoltageWindowConfig":
        if self.upper_v <= self.lower_v:
            raise ValueError("upper_v must be greater than lower_v")
        return self


class SamplingConfig(DomainModel):
    pre_wait_s: NonNegativeFloat = 0.0
    sample_interval_s: NonNegativeFloat = 0.001


class VoltagePointConfig(DomainModel):
    start_v: PotentialFloat
    end_v: PotentialFloat
    step_v: PositiveFloat

    @model_validator(mode="after")
    def _validate_range(self) -> "VoltagePointConfig":
        if self.start_v == self.end_v:
            raise ValueError("voltage point range requires start_v and end_v to be different")
        return self


class TimeSegmentConfig(DomainModel):
    duration_minutes: NonNegativeFloat = 0.0
    point_count: int = Field(default=0, ge=0, le=500)

    @model_validator(mode="after")
    def _validate_zero_duration(self) -> "TimeSegmentConfig":
        if self.duration_minutes == 0 and self.point_count > 0:
            raise ValueError("point_count must be 0 when segment duration is 0")
        return self


class TimePointConfig(DomainModel):
    early: TimeSegmentConfig = Field(default_factory=TimeSegmentConfig)
    plateau: TimeSegmentConfig = Field(default_factory=TimeSegmentConfig)
    late: TimeSegmentConfig = Field(default_factory=TimeSegmentConfig)
    time_basis_mode: TimeBasisMode = TimeBasisMode.ACTIVE_PROGRESS
    manual_eis_duration_s: PositiveFloat | None = None

    @property
    def total_minutes(self) -> float:
        return self.early.duration_minutes + self.plateau.duration_minutes + self.late.duration_minutes

    @property
    def total_point_count(self) -> int:
        return self.early.point_count + self.plateau.point_count + self.late.point_count

    @model_validator(mode="after")
    def _validate_payload(self) -> "TimePointConfig":
        if self.total_point_count <= 0:
            raise ValueError("at least one time segment must define point_count > 0")
        if self.total_minutes <= 0:
            raise ValueError("total time duration must be greater than 0")
        if self.time_basis_mode is TimeBasisMode.INTERRUPTION_COMPENSATED and self.manual_eis_duration_s is None:
            raise ValueError("manual_eis_duration_s is required in interruption_compensated mode")
        return self


class ImpedanceConfig(DomainModel):
    use_open_circuit_init_e: bool = True
    init_e_v: PositiveFloat | None = None
    high_frequency_hz: PositiveFloat = 100000.0
    low_frequency_hz: PositiveFloat = 0.01
    amplitude_v: PositiveFloat = 0.005
    quiet_time_s: NonNegativeFloat = 2.0
    points_per_decade: int = Field(default=10, ge=1)
    auto_sens: bool = True
    fit: bool = True

    @model_validator(mode="after")
    def _validate_config(self) -> "ImpedanceConfig":
        if self.high_frequency_hz <= self.low_frequency_hz:
            raise ValueError("high_frequency_hz must be greater than low_frequency_hz")
        if not self.use_open_circuit_init_e and self.init_e_v is None:
            raise ValueError("init_e_v is required when use_open_circuit_init_e is false")
        return self


class PhaseBase(DomainModel):
    label: str = Field(min_length=1)
    phase_kind: PhaseKind


class ControlledPhaseBase(PhaseBase):
    direction: ProcessDirection = ProcessDirection.DISCHARGE
    current_setpoint: CurrentSetpointConfig = Field(default_factory=CurrentSetpointConfig)
    voltage_window: VoltageWindowConfig = Field(default_factory=VoltageWindowConfig)
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    insert_eis_after_each_point: bool = True


class TimePointPhase(ControlledPhaseBase):
    phase_kind: Literal[PhaseKind.TIME_POINTS] = PhaseKind.TIME_POINTS
    time_points: TimePointConfig


class VoltagePointPhase(ControlledPhaseBase):
    phase_kind: Literal[PhaseKind.VOLTAGE_POINTS] = PhaseKind.VOLTAGE_POINTS
    voltage_points: VoltagePointConfig


class RestPhase(PhaseBase):
    phase_kind: Literal[PhaseKind.REST] = PhaseKind.REST
    duration_s: PositiveFloat


ExperimentPhase = TimePointPhase | VoltagePointPhase | RestPhase


class ExperimentSequenceRequest(DomainModel):
    kind: Literal[ScriptKind.SEQUENCE] = ScriptKind.SEQUENCE
    project: ProjectConfig
    battery: BatteryConfig
    current_basis: CurrentBasisConfig = Field(default_factory=CurrentBasisConfig)
    impedance_defaults: ImpedanceConfig = Field(default_factory=ImpedanceConfig)
    phases: list[ExperimentPhase] = Field(default_factory=list, min_length=1, max_length=20)


class RelaxationMode(StrEnum):
    REST = "rest"
    CONSTANT_CURRENT = "constant_current"


class PulseCurrentConfig(DomainModel):
    mode: CurrentInputMode = CurrentInputMode.RATE
    rate_c: PositiveFloat | None = Field(default=0.1)
    current_a: PositiveFloat | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "PulseCurrentConfig":
        if self.mode is CurrentInputMode.RATE and self.rate_c is None:
            raise ValueError("rate mode requires rate_c")
        if self.mode is CurrentInputMode.ABSOLUTE and self.current_a is None:
            raise ValueError("absolute mode requires current_a")
        return self


class PulseConfig(DomainModel):
    relaxation_mode: RelaxationMode = RelaxationMode.REST
    relaxation_time_s: PositiveFloat = 60.0
    relaxation_current: PulseCurrentConfig | None = None
    pulse_current: PulseCurrentConfig = Field(default_factory=PulseCurrentConfig)
    pulse_duration_s: PositiveFloat = 5.0
    pulse_count: int = Field(default=1, ge=1, le=1000)
    sample_interval_s: NonNegativeFloat = 0.001

    @model_validator(mode="after")
    def _validate_relaxation(self) -> "PulseConfig":
        if self.relaxation_mode is RelaxationMode.CONSTANT_CURRENT and self.relaxation_current is None:
            raise ValueError("relaxation_current is required for constant-current relaxation")
        return self


class ExperimentRequest(DomainModel):
    """Legacy compatibility surface for pulse and minimal old callers."""

    kind: ScriptKind = ScriptKind.PULSE
    project: ProjectConfig
    battery: BatteryConfig
    current_basis: CurrentBasisConfig = Field(default_factory=CurrentBasisConfig)
    direction: ProcessDirection = ProcessDirection.DISCHARGE
    discharge_current: CurrentSetpointConfig = Field(default_factory=CurrentSetpointConfig)
    voltage_window: VoltageWindowConfig = Field(default_factory=VoltageWindowConfig)
    sampling: SamplingConfig = Field(default_factory=SamplingConfig)
    impedance: ImpedanceConfig = Field(default_factory=ImpedanceConfig)
    voltage_points: VoltagePointConfig | None = None
    time_points: TimePointConfig | None = None
    pulse: PulseConfig | None = None


class ValidationIssue(DomainModel):
    severity: Severity
    code: str
    message: str
    field: str | None = None
    hint: str | None = None


class ValidationResult(DomainModel):
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    summary: str = ""

    @property
    def can_generate(self) -> bool:
        return not self.errors


class CurrentResolution(DomainModel):
    one_c_current_a: PositiveFloat
    operating_current_a: PositiveFloat
    operating_rate_c: PositiveFloat


class PointPlan(DomainModel):
    points: list[float] = Field(default_factory=list)
    deltas: list[float] = Field(default_factory=list)
    actual_points: list[float] = Field(default_factory=list)
    compensation_offsets: list[float] = Field(default_factory=list)

    @property
    def compensation_total(self) -> float:
        if not self.compensation_offsets:
            return 0.0
        return float(self.compensation_offsets[-1])


class PhaseRenderPlan(DomainModel):
    phase_index: int
    label: str
    phase_kind: PhaseKind
    direction: ProcessDirection | None = None
    effective_points: list[float] = Field(default_factory=list)
    rendered_points: list[float] = Field(default_factory=list)
    deltas_s: list[float] = Field(default_factory=list)
    compensation_offsets_min: list[float] = Field(default_factory=list)
    point_count: int = 0
    eis_count: int = 0
    wall_clock_total_s: float = 0.0
    insert_eis_after_each_point: bool = False
    time_basis_mode: TimeBasisMode | None = None


class ScriptBundle(DomainModel):
    kind: ScriptKind = ScriptKind.SEQUENCE
    commented_script: str = ""
    minimal_script: str = ""
    issues: list[ValidationIssue] = Field(default_factory=list)
    one_c_current_a: float | None = None
    summary_lines: list[str] = Field(default_factory=list)

    @property
    def can_generate(self) -> bool:
        return not any(issue.severity is Severity.ERROR for issue in self.issues)


class SequenceScriptBundle(ScriptBundle):
    kind: ScriptKind = ScriptKind.SEQUENCE
    phase_plans: list[PhaseRenderPlan] = Field(default_factory=list)
    total_wall_clock_s: float = 0.0
    total_point_count: int = 0
    total_eis_count: int = 0


__all__ = [
    "BatteryConfig",
    "CurrentBasisConfig",
    "CurrentBasisMode",
    "CurrentInputMode",
    "CurrentResolution",
    "CurrentSetpointConfig",
    "DomainModel",
    "ExperimentPhase",
    "ExperimentRequest",
    "ExperimentSequenceRequest",
    "ImpedanceConfig",
    "IssueSeverity",
    "PhaseKind",
    "PhaseRenderPlan",
    "PlanningStrategy",
    "PointPlan",
    "ProcessDirection",
    "ProjectConfig",
    "PulseConfig",
    "PulseCurrentConfig",
    "RelaxationMode",
    "RestPhase",
    "SamplingConfig",
    "ScriptBundle",
    "ScriptKind",
    "ScriptVariant",
    "SequenceScriptBundle",
    "Severity",
    "TimeBasisMode",
    "TimePointConfig",
    "TimePointPhase",
    "TimeSegmentConfig",
    "ValidationIssue",
    "ValidationResult",
    "VoltagePointConfig",
    "VoltagePointPhase",
    "VoltageWindowConfig",
]
