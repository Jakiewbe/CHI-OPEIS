from __future__ import annotations

import pytest
from pydantic import ValidationError

from opeis_master.domain.calculations import normalize_current_input
from opeis_master.domain.contracts import CurrentInputConfig, CurrentInputMode, RateCurrentReference, TimeSegment, TimeUnit, TimepointPlan


def test_current_input_config_supports_direct_and_rate_based_paths() -> None:
    direct = CurrentInputConfig(mode=CurrentInputMode.DIRECT_1C, one_c_current_a=0.0008)
    inferred = CurrentInputConfig(
        mode=CurrentInputMode.INFERRED_FROM_RATE,
        reference=RateCurrentReference(rate_c=0.05, current_a=0.00004),
    )

    assert normalize_current_input(direct).one_c_current_a == pytest.approx(0.0008)
    assert normalize_current_input(inferred).one_c_current_a == pytest.approx(0.0008)


def test_time_segment_and_plan_validate_and_convert() -> None:
    segment = TimeSegment(start=2, end=10, point_count=3)
    plan = TimepointPlan(unit=TimeUnit.MINUTE, segments=[segment])

    assert plan.to_seconds([2, 10]) == pytest.approx([120, 600])

    with pytest.raises(ValidationError):
        TimeSegment(start=1, end=2, point_count=2, include_start=False, include_end=False)
