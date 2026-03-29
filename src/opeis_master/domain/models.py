"""Typed domain contracts for normalization, planning, and compatibility imports."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from opeis_master.domain.enums import CurrentInputMode, ScriptScenario, StepType, TimeUnit

PositiveCurrentA = Annotated[float, Field(gt=0)]
PositiveCRate = Annotated[float, Field(gt=0)]
PositiveFrequencyHz = Annotated[float, Field(gt=0)]
PositiveVoltageV = Annotated[float, Field(gt=0)]
PositiveTimeValue = Annotated[float, Field(gt=0)]
NonNegativeTimeValue = Annotated[float, Field(ge=0)]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)


class ValidationIssue(DomainModel):
    field: str | None = None
    message: str
    severity: Literal["error", "warning"] = "error"
    code: str | None = None


class ValidationReport(DomainModel):
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    summary: str = ""

    @property
    def can_generate(self) -> bool:
        return not self.errors


class GenerationResult(ValidationReport):
    script: str = ""


ValidationResult = ValidationReport


class RateCurrentReference(DomainModel):
    rate_c: PositiveCRate
    current_a: PositiveCurrentA


class CurrentBasis(DomainModel):
    active_mass_g: float | None = Field(default=None, gt=0)
    specific_capacity_mah_g: float | None = Field(default=None, gt=0)
    reference_rate_c: float | None = Field(default=None, gt=0)
    reference_current_a: float | None = Field(default=None, gt=0)
    explicit_one_c_current_a: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _require_one_resolution_path(self) -> "CurrentBasis":
        if self.explicit_one_c_current_a is not None:
            return self
        if self.reference_rate_c is not None and self.reference_current_a is not None:
            return self
        if self.active_mass_g is not None and self.specific_capacity_mah_g is not None:
            return self
        raise ValueError(
            "At least one 1C resolution path is required: explicit 1C, mass/capacity, or rate/current."
        )


class CurrentSolution(DomainModel):
    one_c_current_a: PositiveCurrentA
    source: str
    from_explicit_value: bool = False
    from_mass_capacity: bool = False
    from_reference_rate: bool = False


class ControlCurrent(DomainModel):
    rate_c: float | None = Field(default=None, gt=0)
    current_a: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _require_rate_or_current(self) -> "ControlCurrent":
        if self.rate_c is None and self.current_a is None:
            raise ValueError("Either rate_c or current_a is required.")
        return self


class CurrentInputConfig(DomainModel):
    mode: CurrentInputMode
    one_c_current_a: PositiveCurrentA | None = None
    reference: RateCurrentReference | None = None

    @model_validator(mode="after")
    def _validate_mode_payload(self) -> "CurrentInputConfig":
        if self.mode is CurrentInputMode.DIRECT_1C:
            if self.one_c_current_a is None:
                raise ValueError("one_c_current_a is required when mode is direct_1c.")
            if self.reference is not None:
                raise ValueError("reference must be omitted when mode is direct_1c.")
            return self

        if self.reference is None:
            raise ValueError("reference is required when mode is inferred_from_rate.")
        if self.one_c_current_a is not None:
            raise ValueError("one_c_current_a must be omitted when mode is inferred_from_rate.")
        return self


class NormalizedCurrent(DomainModel):
    input_mode: CurrentInputMode
    one_c_current_a: PositiveCurrentA
    source_rate_c: PositiveCRate | None = None
    source_current_a: PositiveCurrentA | None = None

    @model_validator(mode="after")
    def _validate_source_metadata(self) -> "NormalizedCurrent":
        if self.input_mode is CurrentInputMode.DIRECT_1C:
            if self.source_rate_c is not None or self.source_current_a is not None:
                raise ValueError("Direct 1C inputs must not include source metadata.")
            return self

        if self.source_rate_c is None or self.source_current_a is None:
            raise ValueError("Inferred currents must preserve the source rate/current reference.")
        return self


class TimeSegment(DomainModel):
    start: NonNegativeTimeValue | None = None
    end: PositiveTimeValue | None = None
    point_count: int | None = Field(default=None, ge=1)
    include_start: bool = True
    include_end: bool = True
    start_minute: NonNegativeTimeValue | None = None
    end_minute: NonNegativeTimeValue | None = None
    step_minute: PositiveTimeValue | None = None
    explicit_minutes: list[PositiveTimeValue] | None = None

    @model_validator(mode="after")
    def _validate_geometry(self) -> "TimeSegment":
        if self.explicit_minutes is not None:
            if not self.explicit_minutes:
                raise ValueError("explicit_minutes must not be empty.")
            return self

        if self.start is not None or self.end is not None:
            if self.start is None or self.end is None or self.point_count is None:
                raise ValueError("start, end, and point_count are required for the normalized segment form.")
            if self.point_count < 2:
                raise ValueError("point_count must be at least 2 for the normalized segment form.")
            if self.end <= self.start:
                raise ValueError("end must be greater than start.")
            emitted_points = self.point_count - int(not self.include_start) - int(not self.include_end)
            if emitted_points <= 0:
                raise ValueError("Segment must emit at least one timepoint after endpoint filtering.")
            return self

        if self.start_minute is None or self.end_minute is None:
            raise ValueError("Either explicit_minutes or a start/end range is required.")
        if self.end_minute < self.start_minute:
            raise ValueError("end_minute must be greater than or equal to start_minute.")
        if self.step_minute is None and self.point_count is None:
            raise ValueError("Legacy segment form requires step_minute or point_count.")
        return self


class TimepointPlan(DomainModel):
    unit: TimeUnit = TimeUnit.MINUTE
    segments: list[TimeSegment] = Field(default_factory=list, min_length=1)

    def to_seconds(self, values: list[float]) -> list[float]:
        return [self.unit.to_seconds(value) for value in values]


class RestStepParameters(DomainModel):
    kind: Literal["rest"] = "rest"
    duration_s: PositiveTimeValue


class ConstantCurrentStepParameters(DomainModel):
    kind: Literal["constant_current"] = "constant_current"
    current_a: float
    duration_s: PositiveTimeValue
    rate_c: PositiveCRate | None = None

    @model_validator(mode="after")
    def _validate_non_zero_current(self) -> "ConstantCurrentStepParameters":
        if self.current_a == 0:
            raise ValueError("current_a must be non-zero.")
        return self


class ImpedanceStepParameters(DomainModel):
    kind: Literal["impedance"] = "impedance"
    high_frequency_hz: PositiveFrequencyHz
    low_frequency_hz: PositiveFrequencyHz
    amplitude_v: PositiveVoltageV | None = None
    quiet_time_s: NonNegativeTimeValue = 0.0
    points_per_decade: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_frequency_window(self) -> "ImpedanceStepParameters":
        if self.high_frequency_hz <= self.low_frequency_hz:
            raise ValueError("high_frequency_hz must be greater than low_frequency_hz.")
        return self


class OcvStepParameters(DomainModel):
    kind: Literal["ocv"] = "ocv"
    duration_s: PositiveTimeValue
    sample_interval_s: PositiveTimeValue | None = None


StepParameters = Annotated[
    RestStepParameters
    | ConstantCurrentStepParameters
    | ImpedanceStepParameters
    | OcvStepParameters,
    Field(discriminator="kind"),
]


class ScriptStep(DomainModel):
    step_type: StepType
    label: str | None = None
    parameters: StepParameters

    @model_validator(mode="after")
    def _validate_step_type_match(self) -> "ScriptStep":
        if self.step_type.value != self.parameters.kind:
            raise ValueError("step_type must match parameters.kind.")
        return self


class ScenarioKind(StrEnum):
    FIXED_VOLTAGE = "fixed_voltage"
    TIME_POINTS = "time_points"
    PULSE = "pulse"


class BaseInputs(DomainModel):
    project_name: str = "OPEIS Master"
    save_prefix: str = "opeis"
    file_override: bool = False
    use_open_circuit_init_e: bool = True


class BatteryParameters(DomainModel):
    ocv_voltage_v: PositiveVoltageV = 3.0
    cutoff_voltage_v: PositiveVoltageV = 1.5
    discharge_current_a: PositiveCurrentA = 0.0000865
    pulse_current_a: PositiveCurrentA = 0.001
    pulse_duration_s: PositiveTimeValue = 5.0


class ImpedanceParameters(DomainModel):
    fh_hz: PositiveFrequencyHz = 100000.0
    fl_hz: PositiveFrequencyHz = 0.01
    amp_v: PositiveVoltageV = 0.005
    qt_s: NonNegativeTimeValue = 2.0
    autosens: bool = True


class FixedVoltageScenario(DomainModel):
    target_voltages_v: list[PositiveVoltageV] = Field(default_factory=list)


class TimePointScenario(DomainModel):
    cumulative_times_min: list[PositiveTimeValue] = Field(default_factory=list)


class PulseScenario(DomainModel):
    pulse_current_a: PositiveCurrentA | None = None
    pulse_duration_s: PositiveTimeValue | None = None


class ParsedScriptRequest(DomainModel):
    scenario_kind: ScenarioKind = ScenarioKind.FIXED_VOLTAGE
    base: BaseInputs = Field(default_factory=BaseInputs)
    battery: BatteryParameters = Field(default_factory=BatteryParameters)
    impedance: ImpedanceParameters = Field(default_factory=ImpedanceParameters)
    fixed_voltage: FixedVoltageScenario = Field(default_factory=FixedVoltageScenario)
    time_points: TimePointScenario = Field(default_factory=TimePointScenario)
    pulse: PulseScenario = Field(default_factory=PulseScenario)


class ImpedanceSettings(DomainModel):
    use_ocv_as_init_e: bool = True
    init_e_v: float | None = Field(default=None, gt=0)
    high_frequency_hz: PositiveFrequencyHz = 100000.0
    low_frequency_hz: PositiveFrequencyHz = 0.01
    amplitude_v: PositiveVoltageV = 0.005
    quiet_time_s: NonNegativeTimeValue = 2.0

    @model_validator(mode="after")
    def _validate_init_e_requirement(self) -> "ImpedanceSettings":
        if not self.use_ocv_as_init_e and self.init_e_v is None:
            raise ValueError("init_e_v is required when use_ocv_as_init_e is False.")
        return self


class TimePointRequest(DomainModel):
    kind: Literal["time_points"] = "time_points"
    current_basis: CurrentBasis
    control_current: ControlCurrent
    target_minutes: list[PositiveTimeValue]
    impedance: ImpedanceSettings = Field(default_factory=ImpedanceSettings)
    eh_v: PositiveVoltageV = 3.0
    el_v: PositiveVoltageV = 1.5
    sample_interval_s: PositiveTimeValue = 1.0

    @model_validator(mode="after")
    def _validate_targets(self) -> "TimePointRequest":
        if any(current <= previous for previous, current in zip(self.target_minutes, self.target_minutes[1:])):
            raise ValueError("target_minutes must be strictly increasing.")
        return self


class VoltagePointRequest(DomainModel):
    kind: Literal["voltage_points"] = "voltage_points"
    current_basis: CurrentBasis
    control_current: ControlCurrent
    target_voltages_v: list[PositiveVoltageV]
    estimated_ocv_v: PositiveVoltageV | None = None
    upper_voltage_v: PositiveVoltageV = 3.0
    impedance: ImpedanceSettings = Field(default_factory=ImpedanceSettings)

    @model_validator(mode="after")
    def _validate_targets(self) -> "VoltagePointRequest":
        if not self.target_voltages_v:
            raise ValueError("target_voltages_v must not be empty.")
        return self


class BasicConfig(DomainModel):
    project_name: str = ""
    output_prefix: str = ""
    output_directory: str = ""
    file_override: bool = True


class BatteryConfig(DomainModel):
    chemistry: str = "CFx 半电池"
    capacity_ah: float = Field(1.0, gt=0)
    nominal_voltage_v: float = Field(3.0, gt=0)
    ocv_v: float = Field(3.0, gt=0)
    upper_limit_v: float = Field(3.0, gt=0)
    lower_limit_v: float = Field(1.5, gt=0)
    cell_id: str = ""


class LegacyImpedanceConfig(DomainModel):
    use_ocv_init_e: bool = True
    init_e_v: float | None = Field(default=None, ge=0)
    high_frequency_hz: float = Field(100000.0, gt=0)
    low_frequency_hz: float = Field(0.01, gt=0)
    amplitude_v: float = Field(0.005, ge=0)
    quiet_time_seconds: float = Field(2.0, ge=0)
    auto_sens: bool = True
    impft: bool = True


class FixedVoltageStrategy(DomainModel):
    target_points: list[float] = Field(default_factory=list)
    discharge_current_a: float = Field(0.0000865, gt=0)
    settle_seconds: float = Field(0.0, ge=0)
    sample_interval_s: float = Field(1.0, gt=0)


class TimeSamplingStrategy(DomainModel):
    cumulative_minutes: list[float] = Field(default_factory=list)
    discharge_current_a: float = Field(0.0000865, gt=0)
    segment_delay_seconds: float = Field(0.0, ge=0)
    sample_interval_s: float = Field(1.0, gt=0)


class PulseSequenceStrategy(DomainModel):
    baseline_current_a: float = Field(0.0000865, gt=0)
    baseline_seconds: float = Field(60.0, gt=0)
    pulse_current_a: float = Field(0.001, gt=0)
    pulse_duration_seconds: float = Field(5.0, gt=0)
    rest_duration_seconds: float = Field(0.0, ge=0)
    repeat_count: int = Field(1, ge=1)
    sample_interval_s: float = Field(1.0, gt=0)


class ScriptRequest(DomainModel):
    scenario: ScriptScenario
    basic: BasicConfig
    battery: BatteryConfig
    impedance: LegacyImpedanceConfig
    fixed_voltage: FixedVoltageStrategy = Field(default_factory=FixedVoltageStrategy)
    time_sampling: TimeSamplingStrategy = Field(default_factory=TimeSamplingStrategy)
    pulse_sequence: PulseSequenceStrategy = Field(default_factory=PulseSequenceStrategy)


ImpedanceConfig = LegacyImpedanceConfig
