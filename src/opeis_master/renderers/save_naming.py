"""Save-name policy helpers."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
import re


def format_value_token(value: float) -> str:
    """Build a readable token that stays stable across runs."""

    text = format_decimal(value)
    return text.replace("-", "m").replace(".", "p")


def format_decimal(value: float) -> str:
    """Render a numeric value without scientific notation."""

    decimal_value = Decimal(str(value))
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def sanitize_token(value: str) -> str:
    """Normalize save-name fragments to CHI-friendly ASCII."""

    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "step"


class SaveNameAllocator:
    """Allocate deterministic unique save names within one script."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def allocate(self, preferred: str) -> str:
        base = sanitize_token(preferred)
        self._counts[base] += 1
        count = self._counts[base]
        if count == 1:
            return base
        return f"{base}_{count:02d}"
