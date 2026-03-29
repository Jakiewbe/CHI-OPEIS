"""Validation helpers for the OPEIS domain layer."""

from __future__ import annotations

from collections.abc import Sequence

from opeis_master.domain.contracts import ExperimentConfig, ValidationResult


def ensure_strictly_increasing(values: Sequence[float], *, name: str) -> None:
    for index, (previous, current) in enumerate(zip(values, values[1:]), start=1):
        if current <= previous:
            raise ValueError(
                f"{name} must be strictly increasing; index {index} has {current} after {previous}."
            )


def ensure_positive(values: Sequence[float], *, name: str) -> None:
    for index, value in enumerate(values):
        if value <= 0:
            raise ValueError(f"{name} must contain only positive values; index {index} is {value}.")


class ExperimentValidator:
    """Deterministic validation for the GUI-facing config contract."""

    def validate(self, config: ExperimentConfig) -> ValidationResult:
        result = ValidationResult()

        if config.impedance.fh <= config.impedance.fl:
            result.add_error(field="impedance.fh", message="High frequency must be greater than low frequency.", code="frequency_window_invalid")
            result.add_error(field="impedance.fl", message="Low frequency must be lower than high frequency.", code="frequency_window_invalid")

        if config.eh <= config.el:
            result.add_error(field="eh", message="High potential must be greater than low potential.", code="potential_window_invalid")
            result.add_error(field="el", message="Low potential must be lower than high potential.", code="potential_window_invalid")

        if config.cl < 1:
            result.add_error(field="cl", message="Cycle count must be at least 1.", code="cycle_count_invalid")

        for index, (previous, current) in enumerate(zip(config.time_points_min, config.time_points_min[1:]), start=1):
            if current <= previous:
                result.add_error(field=f"time_points_min[{index}]", message="Time points must be strictly increasing.", code="time_points_not_increasing")
                break

        for index, (previous, current) in enumerate(zip(config.voltage_points_v, config.voltage_points_v[1:]), start=1):
            if current >= previous:
                result.add_error(field=f"voltage_points_v[{index}]", message="Voltage points must be strictly decreasing.", code="voltage_points_not_decreasing")
                break

        if config.impedance.fl <= 0.01 and config.impedance.points_per_decade >= 10:
            result.add_warning(field="impedance.points_per_decade", message="Dense EIS configuration may be too slow at fl=0.01 Hz.", code="dense_eis_low_frequency")

        if config.ocv and config.ocv.enabled and config.ocv.sample_interval_s > 0 and config.ocv.duration_s / config.ocv.sample_interval_s >= 300:
            result.add_warning(field="ocv.sample_interval_s", message="OCV sampling is dense relative to the requested duration.", code="dense_ocv_sampling")

        if len(config.time_points_min) >= 6 or config.imp_insertion_count >= 2:
            result.add_warning(field="time_points_min", message="Repeated IMP insertions will interrupt the discharge profile.", code="intermittent_imp_insertions")

        return result


def validate_experiment_config(config: ExperimentConfig) -> ValidationResult:
    return ExperimentValidator().validate(config)
