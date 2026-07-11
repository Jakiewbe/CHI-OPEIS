from pathlib import Path

from chi_generator.domain.models import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    CurrentInputMode,
    CurrentSetpointConfig,
    DodCapacityBasis,
    DodPointConfig,
    DodPointPhase,
    EisInitStrategy,
    ExperimentPhase,
    ExperimentSequenceRequest,
    ImpedanceConfig,
    ProcessDirection,
    ProjectConfig,
    SamplingConfig,
    ScriptBundle,
    SpacingMode,
    ValidationIssue,
    VoltagePointConfig,
    VoltagePointPhase,
    VoltageWindowConfig,
)


def _base_request(phases: list[ExperimentPhase]) -> ExperimentSequenceRequest:
    return ExperimentSequenceRequest(
        project=ProjectConfig(scheme_name="test", file_prefix="CHI", export_dir=Path(".")),
        battery=BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        impedance_defaults=ImpedanceConfig(
            high_frequency_hz=100000.0,
            low_frequency_hz=1.0,
            amplitude_v=0.005,
            quiet_time_s=2.0,
        ),
        phases=phases,
    )


def _controlled_fields() -> dict[str, object]:
    return {
        "direction": ProcessDirection.DISCHARGE,
        "current_setpoint": CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
        "voltage_window": VoltageWindowConfig(upper_v=3.2, lower_v=1.5),
        "sampling": SamplingConfig(pre_wait_s=0.0, sample_interval_s=1.0),
        "insert_eis_after_each_point": True,
    }


def make_voltage_request(strategy: EisInitStrategy) -> ExperimentSequenceRequest:
    phase = VoltagePointPhase(
        label="voltage",
        voltage_points=VoltagePointConfig(spacing_mode=SpacingMode.MANUAL, manual_points_v=[3.0]),
        eis_init_strategy=strategy,
        manual_init_e_v=2.9 if strategy is EisInitStrategy.MANUAL else None,
        **_controlled_fields(),
    )
    return _base_request([phase])


def make_dod_request(
    points: list[float] | None = None,
    *,
    capacity_basis: DodCapacityBasis = DodCapacityBasis.THEORETICAL,
    reference_capacity_mah: float | None = None,
) -> ExperimentSequenceRequest:
    phase = DodPointPhase(
        label="dod",
        dod_points=DodPointConfig(
            dod_points_percent=points if points is not None else [20.0, 40.0],
            capacity_basis=capacity_basis,
            reference_capacity_mah=reference_capacity_mah,
        ),
        post_trigger_rest_s=0.0,
        **_controlled_fields(),
    )
    return _base_request([phase])


def make_sequence_with_dod_capacities(*capacities_mah: float) -> ExperimentSequenceRequest:
    phases = [
        DodPointPhase(
            label=f"dod-{index}",
            dod_points=DodPointConfig(
                dod_points_percent=[20.0],
                capacity_basis=DodCapacityBasis.USER_REFERENCE,
                reference_capacity_mah=capacity,
            ),
            post_trigger_rest_s=0.0,
            **_controlled_fields(),
        )
        for index, capacity in enumerate(capacities_mah, start=1)
    ]
    return _base_request(phases)


def eis_block_after(script: str, save_line: str) -> str:
    return next(block for block in script.split("\n\n") if save_line in block)


def make_bundle(issue: ValidationIssue) -> ScriptBundle:
    return ScriptBundle(issues=[issue])
