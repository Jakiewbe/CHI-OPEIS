"""Orchestration facade for both domain contracts and legacy scenario workflows."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from opeis_master.domain.calculations import (
    cumulative_timepoints_to_deltas,
    expand_timepoint_plan,
    normalize_current_input,
    timepoint_plan_to_deltas,
)
from opeis_master.domain.contracts import CurrentInputConfig, NormalizedCurrent, TimepointPlan
from opeis_master.domain.enums import ScriptScenario
from opeis_master.domain.models import GenerationResult, ScriptRequest, ValidationIssue


class ScriptGenerationService:
    """Facade that keeps the current/timepoint helpers and the legacy preview/generate flow."""

    def normalize_current(self, config: CurrentInputConfig) -> NormalizedCurrent:
        return normalize_current_input(config)

    def expand_timepoints(self, plan: TimepointPlan) -> list[float]:
        return expand_timepoint_plan(plan)

    def timepoint_deltas(self, plan: TimepointPlan, *, initial_time: float = 0.0) -> list[float]:
        return timepoint_plan_to_deltas(plan, initial_time=initial_time)

    def cumulative_to_deltas(self, timepoints: list[float], *, initial_time: float = 0.0) -> list[float]:
        return cumulative_timepoints_to_deltas(timepoints, initial_time=initial_time)

    def preview(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self._process(raw, render_script=False)

    def validate(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self.preview(raw)

    def generate(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self._process(raw, render_script=True)

    def generate_script(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self.generate(raw)

    def _process(self, raw: Mapping[str, Any], *, render_script: bool) -> GenerationResult:
        request, issues = self._build_request(raw)
        if request is None:
            return GenerationResult(errors=issues, warnings=[], summary="请先修正输入错误。", script="")

        errors, warnings = self._validate_request(request)
        all_errors = [*issues, *errors]
        script = self._render_script(request) if render_script and not all_errors else ""
        return GenerationResult(
            errors=all_errors,
            warnings=warnings,
            summary=f"scenario={request.scenario.value}",
            script=script,
        )

    def _build_request(self, raw: Mapping[str, Any]) -> tuple[ScriptRequest | None, list[ValidationIssue]]:
        issues: list[ValidationIssue] = []

        scenario_text = str(raw.get("basic.scenario", ScriptScenario.TIME_SAMPLING))
        try:
            scenario = ScriptScenario(scenario_text)
        except ValueError:
            scenario = ScriptScenario.TIME_SAMPLING
            issues.append(
                ValidationIssue(
                    field="basic.scenario",
                    message="脚本场景无效。",
                    severity="error",
                )
            )

        payload = {
            "scenario": scenario,
            "basic": {
                "project_name": str(raw.get("basic.project_name", "") or ""),
                "output_prefix": str(raw.get("basic.output_prefix", "") or ""),
                "output_directory": str(raw.get("basic.output_directory", "") or ""),
                "file_override": bool(raw.get("basic.file_override", True)),
            },
            "battery": {
                "chemistry": str(raw.get("battery.chemistry", "CFx 半电池") or "CFx 半电池"),
                "capacity_ah": raw.get("battery.capacity_ah", 1.0),
                "nominal_voltage_v": raw.get("battery.nominal_voltage_v", 3.0),
                "ocv_v": raw.get("battery.ocv_v", 3.0),
                "upper_limit_v": raw.get("battery.upper_limit_v", 3.0),
                "lower_limit_v": raw.get("battery.lower_limit_v", 1.5),
                "cell_id": str(raw.get("battery.cell_id", "") or ""),
            },
            "impedance": {
                "use_ocv_init_e": bool(raw.get("impedance.use_ocv_init_e", True)),
                "init_e_v": raw.get("impedance.init_e_v"),
                "high_frequency_hz": raw.get("impedance.frequency_high_hz", 100000.0),
                "low_frequency_hz": raw.get("impedance.frequency_low_hz", 0.01),
                "amplitude_v": raw.get("impedance.amplitude_v", 0.005),
                "quiet_time_seconds": raw.get("impedance.quiet_time_seconds", 2.0),
                "auto_sens": bool(raw.get("impedance.auto_sens", True)),
                "impft": bool(raw.get("impedance.impft", True)),
            },
            "fixed_voltage": {
                "target_points": self._parse_number_list(
                    raw.get("strategy.fixed_voltage.target_points", ""),
                    "strategy.fixed_voltage.target_points",
                    issues,
                ),
                "discharge_current_a": raw.get("strategy.fixed_voltage.discharge_current_a", 0.0000865),
                "settle_seconds": raw.get("strategy.fixed_voltage.settle_seconds", 0.0),
                "sample_interval_s": raw.get("strategy.fixed_voltage.sample_interval_s", 1.0),
            },
            "time_sampling": {
                "cumulative_minutes": self._parse_number_list(
                    raw.get("strategy.time_sampling.cumulative_minutes", ""),
                    "strategy.time_sampling.cumulative_minutes",
                    issues,
                ),
                "discharge_current_a": raw.get("strategy.time_sampling.discharge_current_a", 0.0000865),
                "segment_delay_seconds": raw.get("strategy.time_sampling.segment_delay_seconds", 0.0),
                "sample_interval_s": raw.get("strategy.time_sampling.sample_interval_s", 1.0),
            },
            "pulse_sequence": {
                "baseline_current_a": raw.get("strategy.pulse_sequence.baseline_current_a", 0.0000865),
                "baseline_seconds": raw.get("strategy.pulse_sequence.baseline_seconds", 60.0),
                "pulse_current_a": raw.get("strategy.pulse_sequence.pulse_current_a", 0.001),
                "pulse_duration_seconds": raw.get("strategy.pulse_sequence.pulse_duration_seconds", 5.0),
                "rest_duration_seconds": raw.get("strategy.pulse_sequence.rest_duration_seconds", 0.0),
                "repeat_count": raw.get("strategy.pulse_sequence.repeat_count", 1),
                "sample_interval_s": raw.get("strategy.pulse_sequence.sample_interval_s", 1.0),
            },
        }

        try:
            return ScriptRequest.model_validate(payload), issues
        except ValidationError as exc:
            issues.extend(self._to_issues(exc))
            return None, issues

    def _validate_request(self, request: ScriptRequest) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        if request.scenario is ScriptScenario.FIXED_VOLTAGE:
            points = request.fixed_voltage.target_points
            if any(current >= previous for previous, current in zip(points, points[1:])):
                errors.append(
                    ValidationIssue(
                        field="strategy.fixed_voltage.target_points",
                        message="固定电压点必须严格递减。",
                        severity="error",
                    )
                )
            if request.impedance.low_frequency_hz <= 0.01 and len(points) >= 6:
                warnings.append(
                    ValidationIssue(
                        field="impedance.frequency_low_hz",
                        message="fl=0.01 且固定电压点较密，阻抗点可能过于密集。",
                        severity="warning",
                    )
                )

        if request.scenario is ScriptScenario.TIME_SAMPLING:
            warnings.append(
                ValidationIssue(
                    field="strategy.time_sampling.cumulative_minutes",
                    message="EIS 时间不计入累计放电时间。",
                    severity="warning",
                )
            )
            warnings.append(
                ValidationIssue(
                    field="strategy.time_sampling.cumulative_minutes",
                    message="生成结果应按带中断的间歇放电曲线理解。",
                    severity="warning",
                )
            )

        return errors, warnings

    def _render_script(self, request: ScriptRequest) -> str:
        prefix = (request.basic.output_prefix or "OPEIS").strip()
        lines: list[str] = []

        if request.scenario is ScriptScenario.TIME_SAMPLING:
            previous = 0.0
            for minute in request.time_sampling.cumulative_minutes:
                delta_seconds = (minute - previous) * 60.0
                previous = minute
                label = self._minute_tag(minute)
                lines.extend(
                    [
                        "tech=istep",
                        f"is1={self._fmt(request.time_sampling.discharge_current_a)}",
                        f"st1={self._fmt(delta_seconds)}",
                        f"eh={self._fmt(request.battery.upper_limit_v)}",
                        f"el={self._fmt(request.battery.lower_limit_v)}",
                        f"si={self._fmt(request.time_sampling.sample_interval_s)}",
                        "cl=1",
                        "run",
                        f"save={prefix}_D{label}",
                        "tech=imp",
                        "eio" if request.impedance.use_ocv_init_e else f"ei={self._fmt(request.impedance.init_e_v or request.battery.ocv_v)}",
                        f"fh={self._fmt(request.impedance.high_frequency_hz)}",
                        f"fl={self._fmt(request.impedance.low_frequency_hz)}",
                        f"amp={self._fmt(request.impedance.amplitude_v)}",
                        f"qt={self._fmt(request.impedance.quiet_time_seconds)}",
                        "impautosens" if request.impedance.auto_sens else "",
                        "impft" if request.impedance.impft else "",
                        "run",
                        f"save={prefix}_E{label}",
                    ]
                )

        elif request.scenario is ScriptScenario.FIXED_VOLTAGE:
            for target in request.fixed_voltage.target_points:
                lines.extend(
                    [
                        "tech=cp",
                        f"ic={self._fmt(request.fixed_voltage.discharge_current_a)}",
                        "ia=0",
                        f"eh={self._fmt(request.battery.ocv_v)}",
                        f"el={self._fmt(target)}",
                        "ta=0.05",
                        f"si={self._fmt(request.fixed_voltage.sample_interval_s)}",
                        "cl=1",
                        "prioe",
                        "run",
                        f"save={prefix}_CP",
                        "tech=imp",
                        f"ei={self._fmt(target)}",
                        f"fh={self._fmt(request.impedance.high_frequency_hz)}",
                        f"fl={self._fmt(request.impedance.low_frequency_hz)}",
                        f"amp={self._fmt(request.impedance.amplitude_v)}",
                        f"qt={self._fmt(request.impedance.quiet_time_seconds)}",
                        "impautosens" if request.impedance.auto_sens else "",
                        "impft" if request.impedance.impft else "",
                        "run",
                        f"save={prefix}_IMP",
                    ]
                )

        else:
            repeat = request.pulse_sequence.repeat_count
            for index in range(1, repeat + 1):
                lines.extend(
                    [
                        "tech=imp",
                        "eio" if request.impedance.use_ocv_init_e else f"ei={self._fmt(request.impedance.init_e_v or request.battery.ocv_v)}",
                        f"fh={self._fmt(request.impedance.high_frequency_hz)}",
                        f"fl={self._fmt(request.impedance.low_frequency_hz)}",
                        f"amp={self._fmt(request.impedance.amplitude_v)}",
                        f"qt={self._fmt(request.impedance.quiet_time_seconds)}",
                        "impautosens" if request.impedance.auto_sens else "",
                        "impft" if request.impedance.impft else "",
                        "run",
                        f"save={prefix}_PRE{index:02d}",
                        "tech=istep",
                        f"is1={self._fmt(request.pulse_sequence.pulse_current_a)}",
                        f"st1={self._fmt(request.pulse_sequence.pulse_duration_seconds)}",
                        f"eh={self._fmt(request.battery.upper_limit_v)}",
                        f"el={self._fmt(request.battery.lower_limit_v)}",
                        f"si={self._fmt(request.pulse_sequence.sample_interval_s)}",
                        "cl=1",
                        "run",
                        f"save={prefix}_PULSE{index:02d}",
                        "tech=imp",
                        "eio" if request.impedance.use_ocv_init_e else f"ei={self._fmt(request.impedance.init_e_v or request.battery.ocv_v)}",
                        f"fh={self._fmt(request.impedance.high_frequency_hz)}",
                        f"fl={self._fmt(request.impedance.low_frequency_hz)}",
                        f"amp={self._fmt(request.impedance.amplitude_v)}",
                        f"qt={self._fmt(request.impedance.quiet_time_seconds)}",
                        "impautosens" if request.impedance.auto_sens else "",
                        "impft" if request.impedance.impft else "",
                        "run",
                        f"save={prefix}_POST{index:02d}",
                    ]
                )

        return "\n".join(line for line in lines if line)

    def _to_issues(self, exc: ValidationError) -> list[ValidationIssue]:
        return [
            ValidationIssue(
                field=".".join(str(part) for part in item["loc"]),
                message=item["msg"],
                severity="error",
            )
            for item in exc.errors()
        ]

    def _parse_number_list(
        self,
        raw_value: Any,
        field: str,
        issues: list[ValidationIssue],
    ) -> list[float]:
        text = str(raw_value or "").strip()
        if not text:
            return []

        values: list[float] = []
        for token in re.split(r"[\s,;]+", text):
            if not token:
                continue
            try:
                values.append(float(token))
            except ValueError:
                issues.append(
                    ValidationIssue(
                        field=field,
                        message=f"无法解析数值: {token}",
                        severity="error",
                    )
                )
                return []
        return values

    @staticmethod
    def _minute_tag(value: float) -> str:
        integer = int(value) if float(value).is_integer() else value
        return f"{integer:03d}M" if isinstance(integer, int) else f"{str(integer).replace('.', '_')}M"

    @staticmethod
    def _fmt(value: float) -> str:
        text = f"{value:g}"
        return text


__all__ = ["ScriptGenerationService"]
