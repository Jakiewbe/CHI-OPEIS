from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from opeis_master.core.enums import ScriptScenario


class CoreModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidationIssue(CoreModel):
    field: str | None = None
    message: str
    severity: Literal["error", "warning"]


class GenerationResult(CoreModel):
    errors: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)
    summary: str = ""
    script: str = ""

    @property
    def can_generate(self) -> bool:
        return not self.errors


class BasicConfig(CoreModel):
    project_name: str = ""
    output_prefix: str = ""
    output_directory: str = ""
    file_override: bool = True


class BatteryConfig(CoreModel):
    chemistry: str = "CFx 半电池"
    capacity_ah: float = Field(1.0, gt=0)
    nominal_voltage_v: float = Field(3.0, gt=0)
    ocv_v: float = Field(3.0, gt=0)
    upper_limit_v: float = Field(3.0, gt=0)
    lower_limit_v: float = Field(1.5, gt=0)
    cell_id: str = ""


class ImpedanceConfig(CoreModel):
    use_ocv_init_e: bool = True
    init_e_v: float | None = Field(default=None, ge=0)
    high_frequency_hz: float = Field(100000.0, gt=0)
    low_frequency_hz: float = Field(0.01, gt=0)
    amplitude_v: float = Field(0.005, ge=0)
    quiet_time_seconds: float = Field(2.0, ge=0)
    auto_sens: bool = True
    impft: bool = True


class FixedVoltageStrategy(CoreModel):
    target_points: list[float] = Field(default_factory=list)
    discharge_current_a: float = Field(0.0000865, gt=0)
    settle_seconds: float = Field(0.0, ge=0)
    sample_interval_s: float = Field(1.0, gt=0)


class TimeSamplingStrategy(CoreModel):
    cumulative_minutes: list[float] = Field(default_factory=list)
    discharge_current_a: float = Field(0.0000865, gt=0)
    segment_delay_seconds: float = Field(0.0, ge=0)
    sample_interval_s: float = Field(1.0, gt=0)


class PulseSequenceStrategy(CoreModel):
    baseline_current_a: float = Field(0.0000865, gt=0)
    baseline_seconds: float = Field(60.0, gt=0)
    pulse_current_a: float = Field(0.001, gt=0)
    pulse_duration_seconds: float = Field(5.0, gt=0)
    rest_duration_seconds: float = Field(0.0, ge=0)
    repeat_count: int = Field(1, ge=1)
    sample_interval_s: float = Field(1.0, gt=0)


class ScriptRequest(CoreModel):
    scenario: ScriptScenario
    basic: BasicConfig
    battery: BatteryConfig
    impedance: ImpedanceConfig
    fixed_voltage: FixedVoltageStrategy = Field(default_factory=FixedVoltageStrategy)
    time_sampling: TimeSamplingStrategy = Field(default_factory=TimeSamplingStrategy)
    pulse_sequence: PulseSequenceStrategy = Field(default_factory=PulseSequenceStrategy)
