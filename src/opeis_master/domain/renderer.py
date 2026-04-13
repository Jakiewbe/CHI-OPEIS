"""Scenario renderer for ParsedScriptRequest-based workflows."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from opeis_master.domain.models import ParsedScriptRequest, ScenarioKind


def _fmt(value: float) -> str:
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


@dataclass(frozen=True)
class RenderedStep:
    filename: str | None
    commands: list[str]


class ScriptRenderer:
    def render(self, request: ParsedScriptRequest) -> str:
        return "\n".join(command for step in self.build_steps(request) for command in step.commands)

    def build_steps(self, request: ParsedScriptRequest) -> list[RenderedStep]:
        if request.scenario_kind == ScenarioKind.FIXED_VOLTAGE:
            return self._render_fixed_voltage(request)
        if request.scenario_kind == ScenarioKind.TIME_POINTS:
            return self._render_time_points(request)
        return self._render_pulse(request)

    def _render_fixed_voltage(self, request: ParsedScriptRequest) -> list[RenderedStep]:
        base = request.base
        battery = request.battery
        imp = request.impedance
        scenario = request.fixed_voltage
        steps: list[RenderedStep] = []
        if scenario.pre_measure_ocv:
            steps.append(self._imp_step(base.save_prefix, "ocv", imp, use_ocv=True))
        discharge_high = scenario.cp_high_voltage_v or battery.ocv_voltage_v
        for index, target_voltage in enumerate(scenario.target_voltages_v, start=1):
            discharge_name = self._save_name(base.save_prefix, "cp", f"d{index:03d}")
            upper_v, lower_v = self._cp_limits(
                current_a=battery.discharge_current_a,
                target_v=target_voltage,
                high_v=discharge_high,
                low_v=battery.cutoff_voltage_v,
            )
            steps.append(
                RenderedStep(
                    filename=discharge_name,
                    commands=[
                        "tech=cp",
                        f"ic={_fmt(battery.discharge_current_a)}",
                        f"ia={_fmt(scenario.cp_reverse_current_a)}",
                        f"eh={_fmt(upper_v)}",
                        f"el={_fmt(lower_v)}",
                        f"tc={_fmt(scenario.cp_cathodic_time_s)}",
                        f"ta={_fmt(scenario.cp_hold_seconds)}",
                        "pn=n",
                        f"si={_fmt(scenario.sample_interval_s)}",
                        f"cl={scenario.cp_cycles}",
                        scenario.cp_priority,
                        "run",
                        f"save={discharge_name}",
                    ],
                )
            )
            steps.append(self._imp_step(base.save_prefix, f"e{index:03d}", imp, init_e=target_voltage))
        return steps

    def _render_time_points(self, request: ParsedScriptRequest) -> list[RenderedStep]:
        base = request.base
        imp = request.impedance
        scenario = request.time_points
        steps: list[RenderedStep] = [self._imp_step(base.save_prefix, "ocv", imp, use_ocv=True)]
        previous = 0.0
        for cumulative_time in sorted(scenario.cumulative_times_min):
            delta_minutes = cumulative_time - previous
            previous = cumulative_time
            label = self._format_minutes(cumulative_time)
            discharge_name = self._save_name(base.save_prefix, "istep", f"d{label}")
            steps.append(
                RenderedStep(
                    filename=discharge_name,
                    commands=[
                        "tech=istep",
                        f"is1={_fmt(scenario.discharge_current_a)}",
                        f"st1={_fmt(delta_minutes * 60)}",
                        f"eh={_fmt(scenario.step_voltage_high_v)}",
                        f"el={_fmt(scenario.step_voltage_low_v)}",
                        f"si={_fmt(scenario.sample_interval_s)}",
                        f"cl={scenario.step_count}",
                        "run",
                        f"save={discharge_name}",
                    ],
                )
            )
            steps.append(self._imp_step(base.save_prefix, f"e{label}", imp, use_ocv=base.use_open_circuit_init_e))
        return steps

    def _render_pulse(self, request: ParsedScriptRequest) -> list[RenderedStep]:
        base = request.base
        battery = request.battery
        imp = request.impedance
        scenario = request.pulse
        steps: list[RenderedStep] = [self._imp_step(base.save_prefix, "ocv", imp, use_ocv=True)]
        for repeat in range(1, scenario.repetitions + 1):
            baseline_name = self._save_name(base.save_prefix, "istep", f"b{repeat:02d}")
            steps.append(
                RenderedStep(
                    filename=baseline_name,
                    commands=[
                        "tech=istep",
                        f"is1={_fmt(scenario.baseline_current_a)}",
                        f"st1={_fmt(scenario.baseline_seconds)}",
                        f"eh={_fmt(battery.ocv_voltage_v)}",
                        f"el={_fmt(battery.cutoff_voltage_v)}",
                        f"si={_fmt(scenario.sample_interval_s)}",
                        "cl=1",
                        "run",
                        f"save={baseline_name}",
                    ],
                )
            )
            steps.append(self._imp_step(base.save_prefix, f"p{repeat:02d}", imp, use_ocv=base.use_open_circuit_init_e))
            pulse_name = self._save_name(base.save_prefix, "istep", f"u{repeat:02d}")
            steps.append(
                RenderedStep(
                    filename=pulse_name,
                    commands=[
                        "tech=istep",
                        f"is1={_fmt(scenario.pulse_current_a)}",
                        f"st1={_fmt(scenario.pulse_seconds)}",
                        f"eh={_fmt(battery.ocv_voltage_v)}",
                        f"el={_fmt(battery.cutoff_voltage_v)}",
                        f"si={_fmt(scenario.sample_interval_s)}",
                        "cl=1",
                        "run",
                        f"save={pulse_name}",
                    ],
                )
            )
            steps.append(self._imp_step(base.save_prefix, f"a{repeat:02d}", imp, use_ocv=base.use_open_circuit_init_e))
        return steps

    def _imp_step(
        self,
        prefix: str,
        suffix: str,
        imp: object,
        *,
        use_ocv: bool = False,
        init_e: float | None = None,
    ) -> RenderedStep:
        filename = self._save_name(prefix, "imp", suffix)
        if init_e is None and not use_ocv:
            init_e = getattr(imp, "init_e_v", 0.0)
        commands = [
            "tech=imp",
            "eio" if use_ocv else f"ei={_fmt(init_e or 0)}",
            f"fh={_fmt(getattr(imp, 'fh_hz'))}",
            f"fl={_fmt(getattr(imp, 'fl_hz'))}",
            f"amp={_fmt(getattr(imp, 'amp_v'))}",
            f"qt={_fmt(getattr(imp, 'qt_s'))}",
        ]
        if getattr(imp, "autosens", True):
            commands.append("impautosens")
        if getattr(imp, "fit", True):
            commands.append("impft")
        commands.extend(["run", f"save={filename}"])
        return RenderedStep(filename=filename, commands=commands)

    @staticmethod
    def _save_name(prefix: str, kind: str, suffix: str) -> str:
        clean_prefix = prefix.strip() or "opeis"
        return f"{clean_prefix}_{kind}_{suffix}"

    @staticmethod
    def _format_minutes(value: float) -> str:
        return _fmt(value).replace(".", "_")

    @staticmethod
    def _cp_limits(*, current_a: float, target_v: float, high_v: float, low_v: float) -> tuple[float, float]:
        if current_a < 0:
            return target_v, low_v
        return high_v, target_v
