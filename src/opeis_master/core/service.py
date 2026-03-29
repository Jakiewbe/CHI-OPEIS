from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from opeis_master.core.enums import ScriptScenario
from opeis_master.core.models import GenerationResult, ScriptRequest, ValidationIssue
from opeis_master.core.renderer import ScriptRenderer
from opeis_master.core.validator import ScriptValidator


class ScriptGenerationService:
    def __init__(
        self,
        validator: ScriptValidator | None = None,
        renderer: ScriptRenderer | None = None,
    ) -> None:
        self._validator = validator or ScriptValidator()
        self._renderer = renderer or ScriptRenderer()

    def preview(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self._process(raw, render_script=False)

    def validate(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self.preview(raw)

    def generate(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self._process(raw, render_script=True)

    def generate_script(self, raw: Mapping[str, Any]) -> GenerationResult:
        return self.generate(raw)

    def _process(self, raw: Mapping[str, Any], *, render_script: bool) -> GenerationResult:
        request, parse_errors = self._build_request(raw)
        if request is None:
            return GenerationResult(errors=parse_errors, summary="请先修正输入错误。")

        validation_errors, warnings, summary = self._validator.validate(request)
        all_errors = [*parse_errors, *validation_errors]
        script = self._renderer.render(request) if render_script and not all_errors else ""
        return GenerationResult(errors=all_errors, warnings=warnings, summary=summary, script=script)

    def _build_request(
        self,
        raw: Mapping[str, Any],
    ) -> tuple[ScriptRequest | None, list[ValidationIssue]]:
        issues: list[ValidationIssue] = []

        scenario_text = str(raw.get("basic.scenario", ScriptScenario.TIME_SAMPLING))
        try:
            scenario = ScriptScenario(scenario_text)
        except ValueError:
            scenario = ScriptScenario.TIME_SAMPLING
            issues.append(ValidationIssue(field="basic.scenario", message="脚本场景无效。", severity="error"))

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
                "target_points": self._parse_number_list(raw.get("strategy.fixed_voltage.target_points", ""), "strategy.fixed_voltage.target_points", issues),
                "discharge_current_a": raw.get("strategy.fixed_voltage.discharge_current_a", 0.0000865),
                "settle_seconds": raw.get("strategy.fixed_voltage.settle_seconds", 0.0),
                "sample_interval_s": raw.get("strategy.fixed_voltage.sample_interval_s", 1.0),
            },
            "time_sampling": {
                "cumulative_minutes": self._parse_number_list(raw.get("strategy.time_sampling.cumulative_minutes", ""), "strategy.time_sampling.cumulative_minutes", issues),
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
            issues.extend(
                ValidationIssue(field=".".join(str(part) for part in item["loc"]), message=item["msg"], severity="error")
                for item in exc.errors()
            )
            return None, issues

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
                issues.append(ValidationIssue(field=field, message=f"无法解析数值: {token}", severity="error"))
                return []
        return values
