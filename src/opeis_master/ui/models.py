"""Pydantic models used by the GUI layer."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from opeis_master.domain.models import ValidationResult


class WorkflowMode(StrEnum):
    fixed_voltage = "fixed_voltage"
    fixed_time = "fixed_time"
    segmented_time = "segmented_time"
    activation_main = "activation_main"


class TechniqueMode(StrEnum):
    imp = "imp"
    cp = "cp"
    istep = "istep"
    delay = "delay"


class ScriptVariant(StrEnum):
    commented = "commented"
    minimal = "minimal"


class CurrentInputMode(StrEnum):
    direct_current = "direct_current"
    one_c_reference = "one_c_reference"
    rate_reference = "rate_reference"


class ScriptFormState(BaseModel):
    """Normalized GUI input snapshot."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workflow: WorkflowMode = WorkflowMode.fixed_voltage
    technique: TechniqueMode = TechniqueMode.imp
    output_variant: ScriptVariant = ScriptVariant.commented
    current_mode: CurrentInputMode = CurrentInputMode.direct_current

    active_mass_mg: float = Field(default=12.0, ge=0.0)
    specific_capacity_mah_g: float = Field(default=260.0, ge=0.0)
    direct_current_a: float = Field(default=0.0000865, ge=0.0)
    one_c_current_a: float = Field(default=0.0000865, ge=0.0)
    reference_rate_c: float = Field(default=0.05, ge=0.0)
    reference_rate_current_a: float = Field(default=0.000040136, ge=0.0)

    eh_v: float = Field(default=3.0)
    el_v: float = Field(default=1.5)
    cl: int = Field(default=1, ge=1)

    imp_fh_hz: float = Field(default=100000.0, gt=0.0)
    imp_fl_hz: float = Field(default=0.01, gt=0.0)
    points_per_decade: int = Field(default=10, ge=1)
    imp_amp_v: float = Field(default=0.005, ge=0.0)
    imp_quiet_time_s: float = Field(default=0.0, ge=0.0)
    imp_insertions: int = Field(default=2, ge=0)

    ocv_enabled: bool = True
    ocv_duration_s: float = Field(default=300.0, ge=0.0)
    ocv_sample_interval_s: float = Field(default=1.0, ge=0.0)

    use_ocv_as_init_e: bool = True
    delay_s: float = Field(default=120.0, ge=0.0)
    file_prefix: str = "OCVEIA"
    note: str = ""

    fixed_voltage_points_text: str = "3.2, 3.0, 2.9, 2.7, 2.5"
    fixed_time_points_text: str = "2, 6, 10, 14, 18"
    segmented_time_points_text: str = "2, 6, 10, 14, 18\n30, 50, 70, 90"
    activation_steps_text: str = "0.0000865, 120\n0.000040136, 240"
    main_steps_text: str = "0.0000865, 1800\n0.0000865, 1800"

    cp_ic_a: float = Field(default=0.0000865)
    cp_ia_a: float = Field(default=0.0000865)
    cp_eh_v: float = Field(default=3.0)
    cp_el_v: float = Field(default=1.5)
    cp_tc_s: float = Field(default=0.005, ge=0.0)
    cp_ta_s: float = Field(default=0.05, ge=0.05)
    cp_cl: int = Field(default=1, ge=0)
    cp_priority: str = "prioe"


class PreviewArtifact(BaseModel):
    """Result returned to the GUI after preview processing."""

    model_config = ConfigDict(extra="forbid")

    commented_script: str = ""
    minimal_script: str = ""
    validation: ValidationResult
    summary: str = ""
    preview_ready: bool = False
