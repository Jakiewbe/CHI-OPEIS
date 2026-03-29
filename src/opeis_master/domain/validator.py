"""Validation for ParsedScriptRequest workflows."""

from __future__ import annotations

from opeis_master.domain.models import ParsedScriptRequest, ScenarioKind, ValidationReport


class ScriptValidator:
    def validate(self, request: ParsedScriptRequest) -> ValidationReport:
        errors: list[str] = []
        warnings: list[str] = []
        base = request.base
        battery = request.battery
        impedance = request.impedance

        if not base.save_prefix.strip():
            warnings.append("鏂囦欢鍚嶅墠缂€涓虹┖")

        if impedance.fl_hz <= 0.01:
            if request.scenario_kind == ScenarioKind.FIXED_VOLTAGE and len(request.fixed_voltage.target_voltages_v) >= 4:
                warnings.append("fl=0.01 fixed-voltage points are dense.")
            if request.scenario_kind == ScenarioKind.TIME_POINTS and len(request.time_points.cumulative_times_min) >= 8:
                warnings.append("fl=0.01 time-point insertions are dense.")

        if request.scenario_kind in {ScenarioKind.TIME_POINTS, ScenarioKind.PULSE}:
            warnings.append("闂存瓏/涓柇鏀剧數")

        if request.scenario_kind == ScenarioKind.FIXED_VOLTAGE:
            near_ocv = [v for v in request.fixed_voltage.target_voltages_v if abs(v - battery.ocv_voltage_v) <= 0.2]
            if len(near_ocv) >= 3:
                warnings.append("OCV 闄勮繎鐢靛帇鐐硅繃瀵?")

        if battery.ocv_voltage_v <= battery.cutoff_voltage_v:
            errors.append("OCV must be higher than cutoff voltage.")

        return ValidationReport(
            errors=errors,
            warnings=warnings,
            summary=f"鍦烘櫙: {request.scenario_kind.value}",
        )
