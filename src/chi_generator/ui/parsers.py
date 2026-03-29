"""Presentation-layer parsing helpers."""

from __future__ import annotations

import re


_NUMBER_PATTERN = re.compile(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")


def parse_float(raw: str, *, field_label: str) -> float:
    text = str(raw).strip()
    if not text:
        raise ValueError(f"{field_label} 不能为空。")
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{field_label} 不是合法数字。") from exc


def parse_int(raw: str, *, field_label: str) -> int:
    text = str(raw).strip()
    if not text:
        raise ValueError(f"{field_label} 不能为空。")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_label} 不是合法整数。") from exc


def parse_number_list(raw_text: str) -> list[float]:
    if not raw_text.strip():
        return []
    return [float(match.group(0)) for match in _NUMBER_PATTERN.finditer(raw_text)]


def parse_segment_rows(raw_text: str) -> list[tuple[float, float, int]]:
    rows: list[tuple[float, float, int]] = []
    for line in raw_text.splitlines():
        values = parse_number_list(line)
        if len(values) >= 3:
            rows.append((values[0], values[1], int(values[2])))
    return rows


def parse_activation_rows(raw_text: str) -> list[tuple[float, str]]:
    rows: list[tuple[float, str]] = []
    for line in raw_text.splitlines():
        text = line.strip()
        if not text:
            continue
        parts = [part.strip() for part in re.split(r"[,;]", text, maxsplit=1)]
        if len(parts) != 2:
            continue
        rows.append((parse_float(parts[0], field_label="活化时长"), parts[1]))
    return rows


def parse_current_token(raw: str) -> tuple[str, float]:
    text = raw.strip().lower()
    if text.endswith("c"):
        return "rate", parse_float(text[:-1], field_label="倍率")
    return "absolute", parse_float(text, field_label="电流")


__all__ = [
    "parse_activation_rows",
    "parse_current_token",
    "parse_float",
    "parse_int",
    "parse_number_list",
    "parse_segment_rows",
]
