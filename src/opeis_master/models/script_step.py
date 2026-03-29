"""Normalized script step models for CHI rendering."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import IMPMeasurementMode, PriorityMode, RenderMode, TechType


class StepBase(BaseModel):
    """Base normalized step."""

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    save_tag: str | None = Field(
        default=None,
        description="Optional readable context token for save name generation.",
    )
    comment: str | None = Field(
        default=None,
        description="Optional human-readable description for commented rendering.",
    )


class IMPStep(StepBase):
    """Normalized AC impedance step."""

    tech: Literal[TechType.IMP] = TechType.IMP
    use_open_circuit: bool = Field(
        default=False,
        description="Render eio instead of explicit ei when true.",
    )
    initial_potential: float | None = Field(
        default=None,
        ge=-10,
        le=10,
        description="Explicit initial potential in V when not using OCP.",
    )
    high_frequency: float = Field(..., gt=0)
    low_frequency: float = Field(..., gt=0)
    amplitude: float = Field(..., gt=0)
    quiet_time: float = Field(..., ge=0)
    auto_sensitivity: bool = True
    measurement_mode: IMPMeasurementMode = IMPMeasurementMode.FT

    @model_validator(mode="after")
    def validate_init_potential_source(self) -> "IMPStep":
        if self.use_open_circuit and self.initial_potential is not None:
            raise ValueError(
                "IMP step cannot set both use_open_circuit=True and initial_potential."
            )
        if not self.use_open_circuit and self.initial_potential is None:
            raise ValueError(
                "IMP step requires initial_potential when use_open_circuit is False."
            )
        return self


class CPStep(StepBase):
    """Normalized chronopotentiometry step."""

    tech: Literal[TechType.CP] = TechType.CP
    cathodic_current: float = Field(..., ge=0, le=0.25)
    anodic_current: float = Field(..., ge=0, le=0.25)
    high_potential: float = Field(..., ge=-10, le=10)
    low_potential: float = Field(..., ge=-10, le=10)
    cathodic_time: float = Field(..., ge=0.005)
    anodic_time: float = Field(..., ge=0.05)
    first_polarity: Literal["p", "n"]
    sample_interval: float = Field(..., ge=0.0025, le=32)
    segments: int = Field(..., ge=1)
    priority: PriorityMode


class ISTEPSegment(BaseModel):
    """Single current-time pair for ISTEP."""

    model_config = ConfigDict(extra="forbid")

    current: float = Field(..., ge=-2, le=2)
    duration: float = Field(..., ge=0, le=10000)


class ISTEPStep(StepBase):
    """Normalized multi-current step technique."""

    tech: Literal[TechType.ISTEP] = TechType.ISTEP
    steps: list[ISTEPSegment] = Field(..., min_length=1, max_length=12)
    high_potential: float = Field(..., ge=-10, le=10)
    low_potential: float = Field(..., ge=-10, le=10)
    sample_interval: float = Field(..., gt=0, le=1)
    cycles: int = Field(..., ge=1, le=10000)


class DelayStep(StepBase):
    """Normalized delay command."""

    tech: Literal[TechType.DELAY] = TechType.DELAY
    duration: int = Field(..., ge=1, le=32000)


ScriptStep = Annotated[
    IMPStep | CPStep | ISTEPStep | DelayStep,
    Field(discriminator="tech"),
]


class ScriptPlan(BaseModel):
    """A validated ordered list of normalized steps."""

    model_config = ConfigDict(extra="forbid")

    steps: list[ScriptStep] = Field(default_factory=list)
