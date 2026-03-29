"""CHI Macro Command renderer."""

from __future__ import annotations

from typing import Iterable

from pydantic import TypeAdapter

from opeis_master.models import (
    CPStep,
    DelayStep,
    IMPMeasurementMode,
    IMPStep,
    ISTEPStep,
    PriorityMode,
    RenderMode,
    ScriptStep,
    TechType,
)
from opeis_master.renderers.save_naming import (
    SaveNameAllocator,
    format_decimal,
    format_value_token,
)

_STEP_LIST_ADAPTER = TypeAdapter(list[ScriptStep])


def render_chi_script(
    steps: Iterable[ScriptStep | dict], mode: RenderMode | str = RenderMode.MINIMAL
) -> str:
    """Render normalized script steps into CHI Macro Command text."""

    render_mode = RenderMode(mode)
    validated_steps = _STEP_LIST_ADAPTER.validate_python(list(steps))
    allocator = SaveNameAllocator()
    blocks: list[str] = []

    for index, step in enumerate(validated_steps, start=1):
        blocks.append(_render_step(step=step, index=index, allocator=allocator, mode=render_mode))

    separator = "\n\n" if render_mode is RenderMode.COMMENTED else "\n"
    return separator.join(blocks)


def _render_step(
    *,
    step: ScriptStep,
    index: int,
    allocator: SaveNameAllocator,
    mode: RenderMode,
) -> str:
    if isinstance(step, IMPStep):
        return _render_imp(step=step, index=index, allocator=allocator, mode=mode)
    if isinstance(step, CPStep):
        return _render_cp(step=step, index=index, allocator=allocator, mode=mode)
    if isinstance(step, ISTEPStep):
        return _render_istep(step=step, index=index, allocator=allocator, mode=mode)
    if isinstance(step, DelayStep):
        return _render_delay(step=step, index=index, mode=mode)
    raise TypeError(f"Unsupported step type: {type(step)!r}")


def _render_imp(
    *, step: IMPStep, index: int, allocator: SaveNameAllocator, mode: RenderMode
) -> str:
    save_name = allocator.allocate(_default_save_name(step=step, index=index))
    lines: list[str] = []
    if mode is RenderMode.COMMENTED:
        init_label = "ocp" if step.use_open_circuit else f"ei={format_decimal(step.initial_potential or 0)}"
        lines.extend(
            [
                f"; Step {index:03d} IMP -> {save_name}",
                (
                    "; "
                    f"init={init_label}, fh={format_decimal(step.high_frequency)}, "
                    f"fl={format_decimal(step.low_frequency)}, amp={format_decimal(step.amplitude)}, "
                    f"qt={format_decimal(step.quiet_time)}, "
                    f"sens={'auto' if step.auto_sensitivity else 'manual'}, mode={step.measurement_mode.value}"
                ),
            ]
        )
        if step.comment:
            lines.append(f"; {step.comment}")

    lines.append("tech=imp")
    lines.append("eio" if step.use_open_circuit else f"ei={format_decimal(step.initial_potential or 0)}")
    lines.append(f"fh={format_decimal(step.high_frequency)}")
    lines.append(f"fl={format_decimal(step.low_frequency)}")
    lines.append(f"amp={format_decimal(step.amplitude)}")
    lines.append(f"qt={format_decimal(step.quiet_time)}")
    if step.auto_sensitivity:
        lines.append("impautosens")
    else:
        raise ValueError("IMP manual sensitivity rendering is not implemented in the normalized model.")
    lines.append("impft" if step.measurement_mode is IMPMeasurementMode.FT else "impsf")
    lines.append("run")
    lines.append(f"save={save_name}")
    return "\n".join(lines)


def _render_cp(
    *, step: CPStep, index: int, allocator: SaveNameAllocator, mode: RenderMode
) -> str:
    save_name = allocator.allocate(_default_save_name(step=step, index=index))
    lines: list[str] = []
    if mode is RenderMode.COMMENTED:
        lines.extend(
            [
                f"; Step {index:03d} CP -> {save_name}",
                (
                    "; "
                    f"ic={format_decimal(step.cathodic_current)}, ia={format_decimal(step.anodic_current)}, "
                    f"eh={format_decimal(step.high_potential)}, el={format_decimal(step.low_potential)}, "
                    f"tc={format_decimal(step.cathodic_time)}, ta={format_decimal(step.anodic_time)}, "
                    f"pn={step.first_polarity}, si={format_decimal(step.sample_interval)}, "
                    f"cl={step.segments}, priority={step.priority.value}"
                ),
            ]
        )
        if step.comment:
            lines.append(f"; {step.comment}")

    lines.extend(
        [
            "tech=cp",
            f"ic={format_decimal(step.cathodic_current)}",
            f"ia={format_decimal(step.anodic_current)}",
            f"eh={format_decimal(step.high_potential)}",
            f"el={format_decimal(step.low_potential)}",
            f"tc={format_decimal(step.cathodic_time)}",
            f"ta={format_decimal(step.anodic_time)}",
            f"pn={step.first_polarity}",
            f"si={format_decimal(step.sample_interval)}",
            f"cl={step.segments}",
            "prioe" if step.priority is PriorityMode.POTENTIAL else "priot",
            "run",
            f"save={save_name}",
        ]
    )
    return "\n".join(lines)


def _render_istep(
    *, step: ISTEPStep, index: int, allocator: SaveNameAllocator, mode: RenderMode
) -> str:
    save_name = allocator.allocate(_default_save_name(step=step, index=index))
    lines: list[str] = []
    if mode is RenderMode.COMMENTED:
        total_duration = sum(segment.duration for segment in step.steps)
        first_current = step.steps[0].current
        lines.extend(
            [
                f"; Step {index:03d} ISTEP -> {save_name}",
                (
                    "; "
                    f"steps={len(step.steps)}, first_i={format_decimal(first_current)}, "
                    f"total_t={format_decimal(total_duration)}, eh={format_decimal(step.high_potential)}, "
                    f"el={format_decimal(step.low_potential)}, si={format_decimal(step.sample_interval)}, "
                    f"cl={step.cycles}"
                ),
            ]
        )
        if step.comment:
            lines.append(f"; {step.comment}")

    lines.append("tech=istep")
    for position, segment in enumerate(step.steps, start=1):
        lines.append(f"is{position}={format_decimal(segment.current)}")
        lines.append(f"st{position}={format_decimal(segment.duration)}")
    lines.append(f"eh={format_decimal(step.high_potential)}")
    lines.append(f"el={format_decimal(step.low_potential)}")
    lines.append(f"si={format_decimal(step.sample_interval)}")
    lines.append(f"cl={step.cycles}")
    lines.append("run")
    lines.append(f"save={save_name}")
    return "\n".join(lines)


def _render_delay(*, step: DelayStep, index: int, mode: RenderMode) -> str:
    lines: list[str] = []
    if mode is RenderMode.COMMENTED:
        lines.append(f"; Step {index:03d} DELAY {step.duration}s")
        if step.comment:
            lines.append(f"; {step.comment}")
    lines.append(f"delay={step.duration}")
    return "\n".join(lines)


def _default_save_name(*, step: IMPStep | CPStep | ISTEPStep, index: int) -> str:
    if step.save_tag:
        context = step.save_tag
    elif isinstance(step, IMPStep):
        context = "ocp" if step.use_open_circuit else f"ei_{format_value_token(step.initial_potential or 0)}"
    elif isinstance(step, CPStep):
        context = (
            f"ic_{format_value_token(step.cathodic_current)}_"
            f"tc_{format_value_token(step.cathodic_time)}"
        )
    elif isinstance(step, ISTEPStep):
        total_duration = sum(segment.duration for segment in step.steps)
        context = (
            f"i_{format_value_token(step.steps[0].current)}_"
            f"t_{format_value_token(total_duration)}"
        )
    else:
        raise TypeError(f"Save names are not supported for {type(step)!r}")

    tech_token = step.tech.value.lower()
    return f"s{index:03d}_{tech_token}_{context}"
