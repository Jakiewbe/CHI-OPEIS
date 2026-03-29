from __future__ import annotations

from enum import StrEnum


class ScriptScenario(StrEnum):
    FIXED_VOLTAGE = "fixed_voltage"
    TIME_SAMPLING = "time_sampling"
    PULSE_SEQUENCE = "pulse_sequence"

    @property
    def label(self) -> str:
        if self is ScriptScenario.FIXED_VOLTAGE:
            return "固定电压点"
        if self is ScriptScenario.TIME_SAMPLING:
            return "时间取点"
        return "脉冲前后"
