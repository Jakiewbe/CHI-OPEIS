"""Presentation-layer models for the PyQt GUI."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from chi_generator.domain.models import ProcessDirection, TimeBasisMode


class WorkspaceMode(StrEnum):
    SEQUENCE = "sequence"
    PULSE = "pulse"


class CurrentInputUiMode(StrEnum):
    RATE = "rate"
    ABSOLUTE = "absolute"


class PhaseUiKind(StrEnum):
    TIME_POINTS = "time_points"
    VOLTAGE_POINTS = "voltage_points"
    REST = "rest"


class RelaxationUiMode(StrEnum):
    REST = "rest"
    CONSTANT_CURRENT = "constant_current"


class GuiPhaseState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = "工步 1"
    phase_kind: PhaseUiKind = PhaseUiKind.TIME_POINTS
    direction: ProcessDirection = ProcessDirection.DISCHARGE
    current_mode: CurrentInputUiMode = CurrentInputUiMode.RATE
    rate_c: str = "0.1"
    current_a: str = "0.0000865"
    upper_voltage_v: str = "3.2"
    lower_voltage_v: str = "1.5"
    pre_wait_s: str = "0"
    sample_interval_s: str = "0.001"
    insert_eis_after_each_point: bool = True

    voltage_start_v: str = "3.2"
    voltage_end_v: str = "1.5"
    voltage_step_v: str = "0.1"

    time_basis_mode: TimeBasisMode = TimeBasisMode.ACTIVE_PROGRESS
    manual_eis_duration_s: str = "0"
    early_duration_min: str = "20"
    early_point_count: str = "5"
    plateau_duration_min: str = "70"
    plateau_point_count: str = "14"
    late_duration_min: str = "30"
    late_point_count: str = "5"

    rest_duration_s: str = "300"


class GuiState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workspace_mode: WorkspaceMode = WorkspaceMode.SEQUENCE
    scheme_name: str = "CHI 原位阻抗"
    file_prefix: str = "CHI"
    export_dir: str = ""
    active_material_mg: str = "1"
    theoretical_capacity_mah_mg: str = "865"
    phases: list[GuiPhaseState] = Field(default_factory=lambda: [GuiPhaseState()])

    use_open_circuit_init_e: bool = True
    init_e_v: str = "3.2"
    high_frequency_hz: str = "100000"
    low_frequency_hz: str = "0.01"
    amplitude_v: str = "0.005"
    quiet_time_s: str = "2"

    pulse_relaxation_mode: RelaxationUiMode = RelaxationUiMode.REST
    pulse_relaxation_time_s: str = "60"
    pulse_relaxation_current_mode: CurrentInputUiMode = CurrentInputUiMode.RATE
    pulse_relaxation_rate_c: str = "0.02"
    pulse_relaxation_current_a: str = "0.00002"
    pulse_current_mode: CurrentInputUiMode = CurrentInputUiMode.RATE
    pulse_current_rate_c: str = "1"
    pulse_current_a: str = "0.001"
    pulse_duration_s: str = "5"
    pulse_count: str = "1"
    pulse_sample_interval_s: str = "0.001"
    pulse_upper_voltage_v: str = "4"
    pulse_lower_voltage_v: str = "-1"
    pulse_pre_wait_s: str = "0"


class SequencePresetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    workspace_mode: WorkspaceMode = WorkspaceMode.SEQUENCE
    state: GuiState


class RecentPresetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_files: list[str] = Field(default_factory=list)


__all__ = [
    "CurrentInputUiMode",
    "GuiPhaseState",
    "GuiState",
    "PhaseUiKind",
    "RecentPresetDocument",
    "RelaxationUiMode",
    "SequencePresetDocument",
    "WorkspaceMode",
]
