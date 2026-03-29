"""Typed domain contracts used by the new current/timing pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from opeis_master.domain.enums import CurrentInputMode, StepType, TimeUnit

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


class ValidationResult(DomainModel):
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    summary: str = ""

    @property
    def can_generate(self) -> bool:
        return not self.errors

    def add_error(self, *, field: str | None, message: str, code: str | None = None) -> None:
        self.errors.append(ValidationIssue(field=field, message=message, severity="error", code=code))

    def add_warning(self, *, field: str | None, message: str, code: str | None = None) -> None:
        self.warnings.append(
            ValidationIssue(field=field, message=message, severity="warning", code=code)
        )


class ValidationReport(ValidationResult):
    """Alias-style validation summary kept for compatibility."""


class CurrentBasis(DomainModel):
    explicit_one_c_current_a: PositiveCurrentA | None = None
    reference_rate_c: PositiveCRate | None = None
    reference_current_a: PositiveCurrentA | None = None
    mass_capacity_ah: PositiveCurrentA | None = None

    @model_validator(mode="after")
    def _validate_sources(self) -> "CurrentBasis":
        has_explicit = self.explicit_one_c_current_a is not None
        has_reference = self.reference_rate_c is not None or self.reference_current_a is not None
        has_mass = self.mass_capacity_ah is not None
        if not (has_explicit or has_reference or has_mass):
            raise ValueError("At least one current resolution path is required.")
        if self.reference_rate_c is None ^ self.reference_current_a is None:
            raise ValueError("reference_rate_c and reference_current_a must be provided together.")
        return self


class ControlCurrent(DomainModel):
    rate_c: PositiveCRate | None = None
    current_a: PositiveCurrentA | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "ControlCurrent":
        if self.rate_c is None and self.current_a is None:
            raise ValueError("Either rate_c or current_a is required.")
        return self


class RateCurrentReference(DomainModel):
    rate_c: PositiveCRate
    current_a: PositiveCurrentA


class CurrentInputConfig(DomainModel):
    mode: CurrentInputMode
    one_c_current_a: PositiveCurrentA | None = None
    reference: RateCurrentReference | None = None

    @model_validator(mode="after")
    def _validate_payload(self) -> "CurrentInputConfig":
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
    start: NonNegativeTimeValue
    end: PositiveTimeValue
    point_count: int = Field(..., ge=2)
    include_start: bool = True
    include_end: bool = True

    @model_validator(mode="after")
    def _validate_geometry(self) -> "TimeSegment":
        if self.end <= self.start:
            raise ValueError("end must be greater than start.")
        emitted_points = self.point_count - int(not self.include_start) - int(not self.include_end)
        if emitted_points <= 0:
            raise ValueError("Segment must emit at least one timepoint after endpoint filtering.")
        return self


class TimepointPlan(DomainModel):
    unit: TimeUnit = TimeUnit.MINUTE
    segments: list[TimeSegment] = Field(default_factory=list, min_length=1)

    def to_seconds(self, values: list[float]) -> list[float]:
        return [self.unit.to_seconds(value) for value in values]


class ExperimentImpedanceConfig(DomainModel):
    fh: PositiveFrequencyHz = 100000.0
    fl: PositiveFrequencyHz = 0.01
    points_per_decade: int = Field(10, ge=1)


class ExperimentOcvConfig(DomainModel):
    enabled: bool = False
    duration_s: NonNegativeTimeValue = 0.0
    sample_interval_s: PositiveTimeValue = 1.0


class ExperimentConfig(DomainModel):
    eh: PositiveVoltageV = 3.0
    el: PositiveVoltageV = 1.5
    cl: int = Field(1, ge=0)
    time_points_min: list[PositiveTimeValue] = Field(default_factory=list)
    voltage_points_v: list[PositiveVoltageV] = Field(default_factory=list)
    impedance: ExperimentImpedanceConfig = Field(default_factory=ExperimentImpedanceConfig)
    ocv: ExperimentOcvConfig | None = None
    imp_insertion_count: int = 0


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


class RestStepParameters(DomainModel):
    kind: Literal["rest"] = "rest"
    duration_s: PositiveTimeValue


class ConstantCurrentStepParameters(DomainModel):
    kind: Literal["constant_current"] = "constant_current"
    current_a: float
    duration_s: PositiveTimeValue
    rate_c: PositiveCRate | None = None

    @model_validator(mode="after")
    def _validate_current(self) -> "ConstantCurrentStepParameters":
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


class GenerationResult(ValidationResult):
    request: ParsedScriptRequest | None = None
    script: str = ""

    @property
    def report(self) -> ValidationReport:
        return ValidationReport(errors=self.errors, warnings=self.warnings, summary=self.summary)
