import pytest

from chi_generator.domain import calculations
from chi_generator.domain.models import DodCapacityBasis, EisInitStrategy
from chi_generator.domain.service import ScriptGenerationService
from chi_generator.domain.validation import validate_sequence_request
from tests.support.factories import (
    make_dod_request,
    make_sequence_with_dod_capacities,
    make_voltage_request,
)


def _resolve_sequence_capacity_ah(request) -> float:
    resolver = getattr(calculations, "resolve_sequence_capacity_ah", None)
    assert callable(resolver), "resolve_sequence_capacity_ah must be implemented"
    return resolver(request)


def test_dod_reference_capacity_drives_sequence_soc_capacity() -> None:
    request = make_dod_request(
        [20.0],
        capacity_basis=DodCapacityBasis.USER_REFERENCE,
        reference_capacity_mah=2.0,
    )

    assert _resolve_sequence_capacity_ah(request) == pytest.approx(0.002)


def test_conflicting_dod_capacities_are_rejected() -> None:
    result = validate_sequence_request(make_sequence_with_dod_capacities(2.0, 2.5))

    assert [issue.code for issue in result.errors] == ["inconsistent_dod_capacity_basis"]


def test_dod_soc_uses_the_same_reference_capacity_as_planning() -> None:
    request = make_dod_request(
        [20.0],
        capacity_basis=DodCapacityBasis.USER_REFERENCE,
        reference_capacity_mah=2.0,
    )

    bundle = ScriptGenerationService().generate(request)

    assert bundle.soc_trace[-1].soc_percent == pytest.approx(80.0)


def test_eis_duration_is_not_counted_as_constant_current_discharge() -> None:
    request = make_dod_request(
        [90.0],
        capacity_basis=DodCapacityBasis.USER_REFERENCE,
        reference_capacity_mah=0.1,
    )
    request.impedance_defaults = request.impedance_defaults.model_copy(update={"low_frequency_hz": 0.01})

    result = validate_sequence_request(request)

    assert "soc_depletion_risk" not in [issue.code for issue in result.warnings]


def test_voltage_cp_does_not_claim_exact_total_time_or_soc() -> None:
    bundle = ScriptGenerationService().generate(make_voltage_request(EisInitStrategy.TARGET_VOLTAGE))

    assert bundle.total_wall_clock_s is None
    assert bundle.known_wall_clock_s > 0
    assert bundle.soc_prediction_complete is False
    assert bundle.phase_plans[0].timing_complete is False
    assert bundle.phase_plans[0].start_time_s is not None
    assert bundle.phase_plans[0].end_time_s is None
