# Domain Design

`chi_generator.domain` is the stable typed domain surface for CHI-OPEIS.
It exists to give the UI, application, renderer, and tests a shared contract
without embedding calculation logic in the GUI layer.

## Scope

The domain layer owns:

- pydantic 领域模型（配置、工步、校验、渲染计划）
- 电流与 C-rate 换算
- 电压点/时间点/分段时间点规划
- Warning / Error 校验
- CHI Macro Command 纯文本渲染

## Current Input

电流配置通过 `CurrentSetpointConfig` 和 `CurrentBasisConfig` 两种模式：

- `CurrentInputMode.RATE` — 按 C-rate 指定
- `CurrentInputMode.ABSOLUTE` — 按绝对电流指定

下游通过 `CurrentResolution` 获得统一的 `one_c_current_a` + `operating_current_a`。

## Timepoint Planning

时间点规划通过：

- `TimePointConfig` — 支持 segmented / fixed / manual 三种模式
- `expand_time_segments()` — 展开为严格递增的时间点列表
- `cumulative_timepoints_to_deltas()` — 累积时间转增量
- `compensate_time_points()` — 中断补偿
- `capacity_compensate_time_points()` — 等效容量补偿（CTC）

规则：

- 时间点必须严格递增
- 生成的 delta 必须严格为正
- CTC 模式下会缩短电流保持时间以抵消 EIS 容量消耗

## Normalized Steps

渲染层使用 `PhaseRenderPlan`、`PointPlan`、`SocTracePoint` 等中间记录，最终输出 CHI 命令文本。

## Public API

推荐导入路径：

- `from chi_generator.domain import ExperimentSequenceRequest`
- `from chi_generator.domain import ScriptGenerationService`
- `from chi_generator.domain import validate_sequence_request`
- `from chi_generator.domain import ImpedanceConfig, TimePointConfig, VoltagePointConfig`

## Compatibility Layer

仓库仍保留 `opeis_master` 兼容层以支持旧测试路径。新代码应统一使用 `chi_generator.domain`。
