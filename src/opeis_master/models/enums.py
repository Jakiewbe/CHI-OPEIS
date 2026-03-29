"""Shared enums for the OPEIS Master domain and rendering models."""

from __future__ import annotations

from enum import StrEnum


class CurrentInputMode(StrEnum):
    """How the user specifies the 1C current."""

    DIRECT_1C = "direct_1c"
    INFERRED_FROM_RATE = "inferred_from_rate"


class StepType(StrEnum):
    """Normalized step categories used before CHI rendering."""

    REST = "rest"
    CONSTANT_CURRENT = "constant_current"
    IMPEDANCE = "impedance"
    OCV = "ocv"


class TimeUnit(StrEnum):
    """Supported units for segment-based timepoint planning."""

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
    """Supported CHI techniques."""

    IMP = "IMP"
    CP = "CP"
    ISTEP = "ISTEP"
    DELAY = "delay"


class RenderMode(StrEnum):
    """Supported script output modes."""

    MINIMAL = "minimal"
    COMMENTED = "commented"


class IMPMeasurementMode(StrEnum):
    """Supported impedance measurement modes."""

    FT = "ft"
    SF = "sf"


class PriorityMode(StrEnum):
    """CP priority selection."""

    TIME = "time"
    POTENTIAL = "potential"
