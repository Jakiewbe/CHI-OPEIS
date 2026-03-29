"""Validation helpers used by the GUI."""

from __future__ import annotations

import re

from opeis_master.domain.models import ExperimentConfig, ImpedanceConfig, OcvConfig, ValidationResult
from opeis_master.domain.validation import ExperimentValidator

from .models import CurrentInputMode, ScriptFormState, TechniqueMode, WorkflowMode

_NUMBER_PATTERN = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def parse_number_list(raw_text: str) -> list[float]:
    """Parse a number list from comma, space, or newline separated text."""

    if not raw_text.strip():
        return []
    return [float(match.group(0)) for match in _NUMBER_PATTERN.finditer(raw_text)]


def _to_experiment_config(state: ScriptFormState) -> ExperimentConfig:
    ocv = None
    if state.ocv_enabled:
        ocv = OcvConfig(
            enabled=True,
            duration_s=state.ocv_duration_s,
            sample_interval_s=state.ocv_sample_interval_s,
        )
    return ExperimentConfig(
        eh=state.eh_v,
        el=state.el_v,
        cl=state.cl,
        impedance=ImpedanceConfig(
            fh=state.imp_fh_hz,
            fl=state.imp_fl_hz,
            points_per_decade=state.points_per_decade,
        ),
        time_points_min=parse_number_list(state.fixed_time_points_text),
        voltage_points_v=parse_number_list(state.fixed_voltage_points_text),
        ocv=ocv,
        imp_insertion_count=state.imp_insertions,
    )


def evaluate_local_validation(state: ScriptFormState) -> ValidationResult:
    """Run the existing domain validator plus GUI-only checks."""

    result = ExperimentValidator().validate(_to_experiment_config(state))

    if state.current_mode == CurrentInputMode.direct_current and state.direct_current_a <= 0:
        result.add_error(
            field="direct_current_a",
            message="Direct current must be greater than 0.",
            code="current_direct_invalid",
        )
    if state.current_mode == CurrentInputMode.one_c_reference and state.one_c_current_a <= 0:
        result.add_error(
            field="one_c_current_a",
            message="1C current must be greater than 0.",
            code="current_one_c_invalid",
        )
    if state.current_mode == CurrentInputMode.rate_reference:
        if state.reference_rate_c <= 0 or state.reference_rate_current_a <= 0:
            result.add_error(
                field="reference_rate_c",
                message="Rate reference current and C-rate must be greater than 0.",
                code="current_rate_reference_invalid",
            )

    if state.technique == TechniqueMode.delay and state.delay_s == 0:
        result.add_warning(
            field="delay_s",
            message="delay is set to 0 s; the step will not introduce any waiting.",
            code="delay_zero",
        )

    if state.workflow == WorkflowMode.activation_main and state.imp_insertions >= 2:
        result.add_warning(
            field="imp_insertions",
            message="Repeated IMP insertions will make the discharge profile appear intermittent.",
            code="intermittent_imp_insertions",
        )

    return result
