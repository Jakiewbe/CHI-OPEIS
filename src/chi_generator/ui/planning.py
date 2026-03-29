"""Pure planning helpers for the GUI layer."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isclose
from pathlib import Path
import re


_NUMBER_PATTERN = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


@dataclass(slots=True)
class CurrentResolution:
    one_c_current_a: float
    discharge_current_a: float
    discharge_rate_c: float


def parse_float_list(raw_text: str) -> list[float]:
    text = raw_text.strip()
    if not text:
        return []
    return [float(match.group(0)) for match in _NUMBER_PATTERN.finditer(text)]


def sanitize_prefix(raw_text: str, fallback: str = "OPEIS") -> str:
    text = raw_text.strip()
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return clean or fallback


def normalize_output_directory(raw_text: str) -> Path:
    text = raw_text.strip()
    return Path(text) if text else Path.cwd()


def resolve_current(*, active_mass_mg: float, theoretical_capacity_mah_mg: float, mode: str, rate_c: float, current_a: float) -> CurrentResolution:
    # The GUI shows theoretical specific capacity in mAh/g while mass is entered in mg.
    # Keep the legacy parameter name here for compatibility with existing callers.
    one_c_current_a = ((active_mass_mg / 1000.0) * theoretical_capacity_mah_mg) / 1000.0
    if mode == "current":
        discharge_current_a = current_a
        discharge_rate_c = discharge_current_a / one_c_current_a if one_c_current_a > 0 else 0.0
    else:
        discharge_rate_c = rate_c
        discharge_current_a = one_c_current_a * discharge_rate_c
    return CurrentResolution(
        one_c_current_a=one_c_current_a,
        discharge_current_a=discharge_current_a,
        discharge_rate_c=discharge_rate_c,
    )


def allocate_counts(weights: list[float], total_count: int) -> list[int]:
    active = [index for index, weight in enumerate(weights) if weight > 0]
    if not active:
        raise ValueError("at least one positive segment is required")
    if total_count < len(active):
        raise ValueError("point count is too small for the requested segments")

    counts = [0] * len(weights)
    for index in active:
        counts[index] = 1

    remaining = total_count - len(active)
    if remaining <= 0:
        return counts

    weight_sum = sum(weights[index] for index in active)
    raw = [((weights[index] / weight_sum) * remaining) if index in active else 0.0 for index in range(len(weights))]
    floor_values = [int(floor(value)) for value in raw]
    for index in range(len(weights)):
        counts[index] += floor_values[index]

    leftover = remaining - sum(floor_values)
    if leftover > 0:
        frac_order = sorted(
            active,
            key=lambda index: raw[index] - floor_values[index],
            reverse=True,
        )
        for offset in range(leftover):
            counts[frac_order[offset % len(frac_order)]] += 1

    return counts


def plan_voltage_points(*, initial_ocv_v: float, plateau_v: float, cutoff_v: float, point_count: int) -> list[float]:
    if point_count < 3:
        raise ValueError("voltage point count must be at least 3")
    if not (initial_ocv_v > plateau_v > cutoff_v):
        raise ValueError("voltage plan requires initial_ocv_v > plateau_v > cutoff_v")

    early_span = initial_ocv_v - plateau_v
    late_span = plateau_v - cutoff_v
    early_count, late_count = allocate_counts([early_span, late_span], point_count)

    points: list[float] = []
    if early_count:
        for index in range(1, early_count + 1):
            points.append(initial_ocv_v - early_span * (index / early_count))
    if late_count:
        for index in range(1, late_count + 1):
            points.append(plateau_v - late_span * (index / late_count))
    return points


def plan_time_points(*, total_s: float, early_s: float, platform_s: float, late_s: float, point_count: int) -> list[float]:
    if point_count < 3:
        raise ValueError("time point count must be at least 3")
    if any(value < 0 for value in (early_s, platform_s, late_s)):
        raise ValueError("time segments must be non-negative")
    if not isclose(total_s, early_s + platform_s + late_s, rel_tol=1e-9, abs_tol=1e-9):
        raise ValueError("time segments must sum to total_s")

    counts = allocate_counts([early_s, platform_s, late_s], point_count)
    points: list[float] = []
    if counts[0]:
        for index in range(1, counts[0] + 1):
            points.append(early_s * (index / counts[0]))
    if counts[1]:
        base = early_s
        for index in range(1, counts[1] + 1):
            points.append(base + platform_s * (index / counts[1]))
    if counts[2]:
        base = early_s + platform_s
        for index in range(1, counts[2] + 1):
            points.append(base + late_s * (index / counts[2]))
    return points


def format_point_list(values: list[float]) -> str:
    return ", ".join(f"{value:g}" for value in values)
