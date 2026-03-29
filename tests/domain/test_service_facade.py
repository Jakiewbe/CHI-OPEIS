from __future__ import annotations

import pytest

from opeis_master.domain.contracts import CurrentInputConfig, CurrentInputMode, RateCurrentReference, TimeSegment, TimeUnit, TimepointPlan
from opeis_master.domain.services import ScriptGenerationService


def test_script_generation_service_wraps_current_normalization() -> None:
    service = ScriptGenerationService()
    result = service.normalize_current(
        CurrentInputConfig(
            mode=CurrentInputMode.INFERRED_FROM_RATE,
            reference=RateCurrentReference(rate_c=0.5, current_a=0.001),
        )
    )

    assert result.one_c_current_a == pytest.approx(0.002)


def test_script_generation_service_wraps_timepoint_deltas() -> None:
    service = ScriptGenerationService()
    deltas = service.timepoint_deltas(
        TimepointPlan(unit=TimeUnit.SECOND, segments=[TimeSegment(start=5, end=15, point_count=3)])
    )

    assert deltas == pytest.approx([5, 5, 5])
