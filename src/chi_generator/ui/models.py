"""Presentation-layer models for the PySide6 GUI."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from chi_generator.domain.models import ProcessDirection, SamplingMode, TimeBasisMode


class WorkspaceMode(StrEnum):
    SEQUENCE = "sequence"
    PULSE = "pulse"


class CurrentBasisUiMode(StrEnum):
    MATERIAL = "material"
    REFERENCE = "reference"


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


class FixedTimeUiMode(StrEnum):
    INTERVAL = "interval"
    POINT_COUNT = "point_count"


class VoltageInputUiMode(StrEnum):
    RANGE = "range"
    MANUAL = "manual"


class WorkflowItemUiKind(StrEnum):
    PHASE = "phase"
    LOOP = "loop"


class GuiTimeSegmentState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    duration_min: str = "0"
    point_count: str = "0"


class GuiPhaseState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_kind: Literal[WorkflowItemUiKind.PHASE] = WorkflowItemUiKind.PHASE
    label: str = "时间工步 1"
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
    voltage_input_mode: VoltageInputUiMode = VoltageInputUiMode.RANGE
    voltage_manual_points_text: str = ""

    time_basis_mode: TimeBasisMode = TimeBasisMode.ACTIVE_PROGRESS
    sampling_mode: SamplingMode = SamplingMode.SEGMENTED
    manual_points_text: str = ""
    manual_eis_duration_s: str = "700"
    fixed_total_duration_min: str = "120"
    fixed_mode: FixedTimeUiMode = FixedTimeUiMode.INTERVAL
    fixed_interval_min: str = "12"
    fixed_point_count: str = "10"
    segmented_points: list[GuiTimeSegmentState] = Field(
        default_factory=lambda: [
            GuiTimeSegmentState(duration_min="20", point_count="5"),
            GuiTimeSegmentState(duration_min="70", point_count="14"),
            GuiTimeSegmentState(duration_min="30", point_count="5"),
        ]
    )

    rest_duration_s: str = "300"

    @model_validator(mode="after")
    def _normalize_segments(self) -> "GuiPhaseState":
        if not self.segmented_points:
            self.segmented_points = [GuiTimeSegmentState(duration_min="120", point_count="10")]
        return self


class GuiLoopState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_kind: Literal[WorkflowItemUiKind.LOOP] = WorkflowItemUiKind.LOOP
    label: str = "循环块"
    repeat_count: int = Field(default=2, ge=2, le=100)
    expanded: bool = True
    phases: list[GuiPhaseState] = Field(default_factory=lambda: [GuiPhaseState()])

    @model_validator(mode="after")
    def _normalize_phases(self) -> "GuiLoopState":
        if not self.phases:
            self.phases = [GuiPhaseState()]
        return self


WorkflowItemState = Annotated[GuiPhaseState | GuiLoopState, Field(discriminator="item_kind")]


def expand_workflow_items(items: list[WorkflowItemState]) -> list[GuiPhaseState]:
    expanded: list[GuiPhaseState] = []
    for item in items:
        if isinstance(item, GuiLoopState):
            for _ in range(item.repeat_count):
                expanded.extend(phase.model_copy(deep=True) for phase in item.phases)
        else:
            expanded.append(item.model_copy(deep=True))
    return expanded


def _normalize_workflow_payload(items: list[object]) -> list[object]:
    normalized: list[object] = []
    for item in items:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        raw = dict(item)
        if raw.get("item_kind") == WorkflowItemUiKind.LOOP.value or "repeat_count" in raw:
            raw.setdefault("item_kind", WorkflowItemUiKind.LOOP.value)
            phases = raw.get("phases", [])
            if isinstance(phases, list):
                raw["phases"] = _normalize_workflow_payload(phases)
        else:
            raw.setdefault("item_kind", WorkflowItemUiKind.PHASE.value)
        normalized.append(raw)
    return normalized


class GuiDraftState(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    workspace_mode: WorkspaceMode = WorkspaceMode.SEQUENCE
    scheme_name: str = "CHI 原位阻抗"
    file_prefix: str = "CHI"
    export_dir: str = ""
    active_material_mg: str = "1"
    theoretical_capacity_mah_mg: str = "865"
    current_basis_mode: CurrentBasisUiMode = CurrentBasisUiMode.MATERIAL
    reference_rate_c: str = "1"
    reference_current_a: str = "0.000865"
    workflow_items: list[WorkflowItemState] = Field(default_factory=lambda: [GuiPhaseState()])
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

    @model_validator(mode="before")
    @classmethod
    def _compat_before(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        raw = dict(value)
        if raw.get("workspace_mode") == "pulse_in_situ":
            raw["workspace_mode"] = WorkspaceMode.PULSE.value
        raw.pop("impedance_mode", None)
        raw.pop("use_load_init_e", None)
        raw.pop("geis_amplitude_a", None)
        raw.pop("estimated_resistance_ohm", None)
        raw.setdefault("current_basis_mode", CurrentBasisUiMode.MATERIAL.value)
        raw.setdefault("reference_rate_c", "1")
        raw.setdefault("reference_current_a", "0.000865")
        if "workflow_items" not in raw and "phases" in raw:
            raw["workflow_items"] = raw["phases"]
        if "workflow_items" in raw and isinstance(raw["workflow_items"], list):
            raw["workflow_items"] = _normalize_workflow_payload(raw["workflow_items"])
        return raw

    @model_validator(mode="after")
    def _normalize_workflow(self) -> "GuiDraftState":
        if not self.workflow_items:
            self.workflow_items = [GuiPhaseState()]
        self.phases = expand_workflow_items(self.workflow_items)
        return self


class GuiValidatedPhase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: GuiPhaseState


class GuiValidatedState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft: GuiDraftState
    phases: list[GuiValidatedPhase]


GuiState = GuiDraftState


class SequencePresetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 4
    workspace_mode: WorkspaceMode = WorkspaceMode.SEQUENCE
    state: GuiDraftState

    @model_validator(mode="before")
    @classmethod
    def _compat_before(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        raw = dict(value)
        if raw.get("workspace_mode") == "pulse_in_situ":
            raw["workspace_mode"] = WorkspaceMode.PULSE.value
        state = raw.get("state")
        if isinstance(state, dict):
            state = dict(state)
            if state.get("workspace_mode") == "pulse_in_situ":
                state["workspace_mode"] = WorkspaceMode.PULSE.value
            raw["state"] = state
        return raw


class RecentPresetDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent_files: list[str] = Field(default_factory=list)


__all__ = [
    "CurrentBasisUiMode",
    "CurrentInputUiMode",
    "FixedTimeUiMode",
    "GuiDraftState",
    "GuiLoopState",
    "GuiPhaseState",
    "GuiState",
    "GuiTimeSegmentState",
    "GuiValidatedPhase",
    "GuiValidatedState",
    "PhaseUiKind",
    "RecentPresetDocument",
    "RelaxationUiMode",
    "SequencePresetDocument",
    "VoltageInputUiMode",
    "WorkflowItemState",
    "WorkflowItemUiKind",
    "WorkspaceMode",
    "expand_workflow_items",
]
