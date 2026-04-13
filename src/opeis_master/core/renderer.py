from __future__ import annotations

import re

from opeis_master.core.enums import ScriptScenario
from opeis_master.core.models import ScriptRequest


class ScriptRenderer:
    def render(self, request: ScriptRequest) -> str:
        lines: list[str] = []
        if request.basic.file_override:
            lines.append("fileoverride")
        lines.append("cellon")

        if request.scenario is ScriptScenario.FIXED_VOLTAGE:
            lines.extend(self._render_fixed_voltage(request))
        elif request.scenario is ScriptScenario.TIME_SAMPLING:
            lines.extend(self._render_time_sampling(request))
        else:
            lines.extend(self._render_pulse_sequence(request))

        lines.append("celloff")
        return "\n".join(lines)

    def _render_fixed_voltage(self, request: ScriptRequest) -> list[str]:
        lines = self._impedance_block(request, self._filename(request, "OCVEIA"), use_ocv=True)
        for point in request.fixed_voltage.target_points:
            if request.fixed_voltage.settle_seconds > 0:
                lines.append(f"delay={request.fixed_voltage.settle_seconds:g}")
            upper_v, lower_v = self._cp_limits(
                current_a=request.fixed_voltage.discharge_current_a,
                target_v=point,
                high_v=request.battery.upper_limit_v,
                low_v=request.battery.lower_limit_v,
            )
            lines.extend(
                [
                    "tech=cp",
                    f"ic={request.fixed_voltage.discharge_current_a:g}",
                    "ia=0",
                    f"eh={upper_v:g}",
                    f"el={lower_v:g}",
                    "tc=86400",
                    "ta=0.05",
                    f"si={request.fixed_voltage.sample_interval_s:g}",
                    "cl=1",
                    "prioe",
                    "run",
                    f"save={self._filename(request, f'D{self._voltage_label(point)}')}",
                ]
            )
            lines.extend(
                self._impedance_block(
                    request,
                    self._filename(request, f"E{self._voltage_label(point)}"),
                    use_ocv=False,
                    init_e=point,
                )
            )
        return lines

    def _render_time_sampling(self, request: ScriptRequest) -> list[str]:
        lines = self._impedance_block(request, self._filename(request, "OCVEIA"), use_ocv=True)
        previous = 0.0
        for minute in request.time_sampling.cumulative_minutes:
            if request.time_sampling.segment_delay_seconds > 0:
                lines.append(f"delay={request.time_sampling.segment_delay_seconds:g}")
            delta_seconds = (minute - previous) * 60
            previous = minute
            lines.extend(
                [
                    "tech=istep",
                    f"is1={request.time_sampling.discharge_current_a:g}",
                    f"st1={delta_seconds:g}",
                    f"eh={request.battery.upper_limit_v:g}",
                    f"el={request.battery.lower_limit_v:g}",
                    f"si={request.time_sampling.sample_interval_s:g}",
                    "cl=1",
                    "run",
                    f"save={self._filename(request, f'D{self._time_label(minute)}')}",
                ]
            )
            lines.extend(
                self._impedance_block(
                    request,
                    self._filename(request, f"E{self._time_label(minute)}"),
                    use_ocv=request.impedance.use_ocv_init_e,
                    init_e=request.impedance.init_e_v,
                )
            )
        return lines

    def _render_pulse_sequence(self, request: ScriptRequest) -> list[str]:
        lines = self._impedance_block(request, self._filename(request, "OCVEIA"), use_ocv=True)
        strategy = request.pulse_sequence
        for index in range(1, strategy.repeat_count + 1):
            if strategy.rest_duration_seconds > 0:
                lines.append(f"delay={strategy.rest_duration_seconds:g}")
            lines.extend(
                [
                    "tech=istep",
                    f"is1={strategy.baseline_current_a:g}",
                    f"st1={strategy.baseline_seconds:g}",
                    f"eh={request.battery.upper_limit_v:g}",
                    f"el={request.battery.lower_limit_v:g}",
                    f"si={strategy.sample_interval_s:g}",
                    "cl=1",
                    "run",
                    f"save={self._filename(request, f'B{index:02d}')}",
                ]
            )
            lines.extend(
                self._impedance_block(
                    request,
                    self._filename(request, f"PRE{index:02d}"),
                    use_ocv=request.impedance.use_ocv_init_e,
                    init_e=request.impedance.init_e_v,
                )
            )
            lines.extend(
                [
                    "tech=istep",
                    f"is1={strategy.pulse_current_a:g}",
                    f"st1={strategy.pulse_duration_seconds:g}",
                    f"eh={request.battery.upper_limit_v:g}",
                    f"el={request.battery.lower_limit_v:g}",
                    f"si={strategy.sample_interval_s:g}",
                    "cl=1",
                    "run",
                    f"save={self._filename(request, f'P{index:02d}')}",
                ]
            )
            lines.extend(
                self._impedance_block(
                    request,
                    self._filename(request, f"POST{index:02d}"),
                    use_ocv=request.impedance.use_ocv_init_e,
                    init_e=request.impedance.init_e_v,
                )
            )
        return lines

    def _impedance_block(
        self,
        request: ScriptRequest,
        filename: str,
        *,
        use_ocv: bool,
        init_e: float | None = None,
    ) -> list[str]:
        lines = [
            "tech=imp",
            "eio" if use_ocv else f"ei={(init_e if init_e is not None else 0.0):g}",
            f"fh={request.impedance.high_frequency_hz:g}",
            f"fl={request.impedance.low_frequency_hz:g}",
            f"amp={request.impedance.amplitude_v:g}",
            f"qt={request.impedance.quiet_time_seconds:g}",
        ]
        if request.impedance.auto_sens:
            lines.append("impautosens")
        if request.impedance.impft:
            lines.append("impft")
        lines.extend(["run", f"save={filename}"])
        return lines

    def _filename(self, request: ScriptRequest, suffix: str) -> str:
        prefix = request.basic.output_prefix.strip() or "OPEIS"
        clean = re.sub(r"[^A-Za-z0-9_-]+", "_", prefix).strip("_") or "OPEIS"
        return f"{clean}_{suffix}"

    @staticmethod
    def _time_label(value: float) -> str:
        text = f"{value:g}".replace(".", "_")
        return f"{text.zfill(3) if '_' not in text else text}M"

    @staticmethod
    def _voltage_label(value: float) -> str:
        return f"{value:.2f}V"

    @staticmethod
    def _cp_limits(*, current_a: float, target_v: float, high_v: float, low_v: float) -> tuple[float, float]:
        if current_a < 0:
            return target_v, low_v
        return high_v, target_v
