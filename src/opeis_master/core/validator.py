from __future__ import annotations

from opeis_master.core.enums import ScriptScenario
from opeis_master.core.models import ScriptRequest, ValidationIssue


class ScriptValidator:
    def validate(self, request: ScriptRequest) -> tuple[list[ValidationIssue], list[ValidationIssue], str]:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        self._validate_shared(request, errors, warnings)
        if request.scenario is ScriptScenario.FIXED_VOLTAGE:
            self._validate_fixed_voltage(request, errors, warnings)
        elif request.scenario is ScriptScenario.TIME_SAMPLING:
            self._validate_time_sampling(request, errors, warnings)
        else:
            self._validate_pulse_sequence(request, errors, warnings)

        return errors, warnings, self._build_summary(request, errors, warnings)

    def _validate_shared(
        self,
        request: ScriptRequest,
        errors: list[ValidationIssue],
        warnings: list[ValidationIssue],
    ) -> None:
        battery = request.battery
        impedance = request.impedance
        prefix = request.basic.output_prefix.strip()

        if battery.upper_limit_v <= battery.lower_limit_v:
            errors.extend(
                [
                    ValidationIssue(field="battery.upper_limit_v", message="上限电压必须高于下限电压。", severity="error"),
                    ValidationIssue(field="battery.lower_limit_v", message="下限电压必须低于上限电压。", severity="error"),
                ]
            )

        if battery.ocv_v <= battery.lower_limit_v:
            errors.append(
                ValidationIssue(field="battery.ocv_v", message="OCV 必须高于下限电压。", severity="error")
            )

        if impedance.high_frequency_hz <= impedance.low_frequency_hz:
            errors.extend(
                [
                    ValidationIssue(field="impedance.frequency_high_hz", message="高频上限必须大于低频下限。", severity="error"),
                    ValidationIssue(field="impedance.frequency_low_hz", message="低频下限必须小于高频上限。", severity="error"),
                ]
            )

        if not impedance.use_ocv_init_e and impedance.init_e_v is None:
            errors.append(
                ValidationIssue(field="impedance.init_e_v", message="未启用 OCV Init E 时，必须填写 Init E。", severity="error")
            )

        if not prefix:
            warnings.append(
                ValidationIssue(field="basic.output_prefix", message="输出前缀为空，系统会回退为默认前缀，文件名可读性较差。", severity="warning")
            )
        elif len(prefix) < 4 or prefix.strip().lower() in {"run", "test", "data", "tmp", "out", "opeis"}:
            warnings.append(
                ValidationIssue(field="basic.output_prefix", message="输出前缀过于通用，存在文件名重复或难以区分的风险。", severity="warning")
            )

    def _validate_fixed_voltage(
        self,
        request: ScriptRequest,
        errors: list[ValidationIssue],
        warnings: list[ValidationIssue],
    ) -> None:
        points = request.fixed_voltage.target_points
        battery = request.battery

        if not points:
            errors.append(
                ValidationIssue(field="strategy.fixed_voltage.target_points", message="固定电压点场景至少需要一个目标电压点。", severity="error")
            )
            return

        if any(point <= battery.lower_limit_v or point > battery.upper_limit_v for point in points):
            errors.append(
                ValidationIssue(field="strategy.fixed_voltage.target_points", message="目标电压点必须位于电压窗口内，且高于下限电压。", severity="error")
            )

        if any(current >= previous for previous, current in zip(points, points[1:])):
            errors.append(
                ValidationIssue(field="strategy.fixed_voltage.target_points", message="目标电压点必须严格递减。", severity="error")
            )

        near_ocv = [point for point in points if abs(point - battery.ocv_v) <= 0.25]
        if len(near_ocv) >= 3 or any(abs(previous - current) <= 0.1 for previous, current in zip(points, points[1:])):
            warnings.append(
                ValidationIssue(field="strategy.fixed_voltage.target_points", message="OCV 附近电压点过密，可能出现平台被跳过或瞬时极化过大的情况。", severity="warning")
            )

        if request.impedance.low_frequency_hz <= 0.01 and len(points) >= 6:
            warnings.append(
                ValidationIssue(field="impedance.frequency_low_hz", message="fl=0.01 且固定电压点较密，单次阻抗测试会显著拉长总实验时间。", severity="warning")
            )

        if len(points) >= 2:
            warnings.append(
                ValidationIssue(field="strategy.fixed_voltage.target_points", message="每个电压点后插入 EIS 会形成间歇放电曲线，不应视为连续恒流放电。", severity="warning")
            )

    def _validate_time_sampling(
        self,
        request: ScriptRequest,
        errors: list[ValidationIssue],
        warnings: list[ValidationIssue],
    ) -> None:
        points = request.time_sampling.cumulative_minutes

        if not points:
            errors.append(
                ValidationIssue(field="strategy.time_sampling.cumulative_minutes", message="时间取点场景至少需要一个累计时间点。", severity="error")
            )
            return

        if any(point <= 0 for point in points):
            errors.append(
                ValidationIssue(field="strategy.time_sampling.cumulative_minutes", message="累计时间点必须为正数。", severity="error")
            )

        if any(current <= previous for previous, current in zip(points, points[1:])):
            errors.append(
                ValidationIssue(field="strategy.time_sampling.cumulative_minutes", message="累计时间点必须严格递增。", severity="error")
            )

        if request.impedance.low_frequency_hz <= 0.01 and len(points) >= 8:
            warnings.append(
                ValidationIssue(field="impedance.frequency_low_hz", message="fl=0.01 且时间点较密，EIS 时间会明显打断放电节奏。", severity="warning")
            )

        warnings.extend(
            [
                ValidationIssue(field="strategy.time_sampling.cumulative_minutes", message="时间取点场景默认按纯放电累计时间建模，EIS 时间不计入累计放电时间。", severity="warning"),
                ValidationIssue(field="strategy.time_sampling.cumulative_minutes", message="插入 EIS 后得到的是带中断的间歇放电曲线，建议另测纯恒流参考曲线。", severity="warning"),
            ]
        )

    def _validate_pulse_sequence(
        self,
        request: ScriptRequest,
        errors: list[ValidationIssue],
        warnings: list[ValidationIssue],
    ) -> None:
        strategy = request.pulse_sequence

        if strategy.pulse_current_a <= strategy.baseline_current_a:
            warnings.append(
                ValidationIssue(field="strategy.pulse_sequence.pulse_current_a", message="脉冲电流未明显高于基线电流，前后阻抗差异可能不明显。", severity="warning")
            )

        if request.impedance.low_frequency_hz <= 0.01 and strategy.repeat_count >= 3:
            warnings.append(
                ValidationIssue(field="impedance.frequency_low_hz", message="fl=0.01 且脉冲重复次数较多，总测试时间可能明显增长。", severity="warning")
            )

        warnings.append(
            ValidationIssue(field="strategy.pulse_sequence.repeat_count", message="脉冲前后插入 EIS 会中断放电，应按脉冲/间歇流程理解数据。", severity="warning")
        )

    def _build_summary(
        self,
        request: ScriptRequest,
        errors: list[ValidationIssue],
        warnings: list[ValidationIssue],
    ) -> str:
        lines = [
            f"场景: {request.scenario.label}",
            f"输出前缀: {request.basic.output_prefix.strip() or 'OPEIS'}",
            f"电池: {request.battery.chemistry}",
            f"电压窗口: {request.battery.upper_limit_v:g} -> {request.battery.lower_limit_v:g} V",
            (
                "阻抗参数: "
                f"fh={request.impedance.high_frequency_hz:g} Hz, "
                f"fl={request.impedance.low_frequency_hz:g} Hz, "
                f"amp={request.impedance.amplitude_v:g} V, "
                f"qt={request.impedance.quiet_time_seconds:g} s"
            ),
        ]
        if request.scenario is ScriptScenario.FIXED_VOLTAGE:
            lines.append("目标电压点: " + ", ".join(f"{value:g}" for value in request.fixed_voltage.target_points))
        elif request.scenario is ScriptScenario.TIME_SAMPLING:
            lines.append("累计时间点(min): " + ", ".join(f"{value:g}" for value in request.time_sampling.cumulative_minutes))
        else:
            lines.append(
                "脉冲参数: "
                f"baseline={request.pulse_sequence.baseline_current_a:g} A/{request.pulse_sequence.baseline_seconds:g} s, "
                f"pulse={request.pulse_sequence.pulse_current_a:g} A/{request.pulse_sequence.pulse_duration_seconds:g} s, "
                f"repeat={request.pulse_sequence.repeat_count}"
            )
        lines.append(f"错误数: {len(errors)}")
        lines.append(f"告警数: {len(warnings)}")
        return "\n".join(lines)
