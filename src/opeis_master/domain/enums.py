"""Self-contained enums for the OPEIS domain layer."""

from __future__ import annotations

from enum import StrEnum


class CurrentInputMode(StrEnum):
    DIRECT_1C = "direct_1c"
    INFERRED_FROM_RATE = "inferred_from_rate"


class StepType(StrEnum):
    REST = "rest"
    CONSTANT_CURRENT = "constant_current"
    IMPEDANCE = "impedance"
    OCV = "ocv"


class TimeUnit(StrEnum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"

    @property
    def seconds_factor(self) -> float:
        if self is TimeUnit.SECOND:
            return 1.0
        if self is TimeUnit.MINUTE:
            return 60.0
        return 3600.0

    def to_seconds(self, value: float) -> float:
        return value * self.seconds_factor


class TechType(StrEnum):
    IMP = "IMP"
    CP = "CP"
    ISTEP = "ISTEP"
    DELAY = "delay"


class RenderMode(StrEnum):
    MINIMAL = "minimal"
    COMMENTED = "commented"


class IMPMeasurementMode(StrEnum):
    FT = "ft"
    SF = "sf"


class PriorityMode(StrEnum):
    TIME = "time"
    POTENTIAL = "potential"


class ScriptScenario(StrEnum):
    FIXED_VOLTAGE = "fixed_voltage"
    TIME_SAMPLING = "time_sampling"
    PULSE_SEQUENCE = "pulse_sequence"
