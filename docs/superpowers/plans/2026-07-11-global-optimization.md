# OPEISMaster Global Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagents are explicitly prohibited for this project run.

**Goal:** 将 OPEISMaster 收敛为单一业务实现，修正三种 EIS 模式的时间、容量、SoC 与告警语义，并形成可重复验证和发布的 Windows 桌面应用。

**Architecture:** `src/chi_generator/` 是唯一业务实现；`src/opeis_master/` 只保留旧启动入口转发。领域层负责模型、计算、校验和 CHI 命令语义，UI 只负责输入、字段反馈、风险确认和展示。无法由输入参数确定的 CP 时长必须保持未知，不使用估算或兜底值伪造总历时与 SoC。

**Tech Stack:** Python 3.11+、PySide6 6.11+、PySide6-Fluent-Widgets 1.11+、pydantic 2.8+、pytest、pytest-qt、PyInstaller 6.11+、PowerShell。

## Global Constraints

- 不创建分支或 worktree，除非用户后续明确同意。
- 当前 15 个已跟踪文件的未提交修改属于用户现有工作；实施时必须保留并逐项审查，不能覆盖或回退。
- UI 不得包含领域计算；领域层不得依赖 PySide6。
- 最终 CHI 脚本只能包含可直接粘贴到 CHI Macro Command 的纯命令，不能出现公式、解释文字或占位注释。
- Error 阻止生成；高风险 Warning 必须由用户明确确认后才允许复制脚本；确认仅对当前参数和当前风险集合有效。
- CP 到目标电压的时间不能从现有输入准确推导。存在电压取点工步时，总历时和 SoC 必须标记为不完整，禁止补默认时间。
- DOD 规划、校验、摘要和 SoC 必须使用同一个容量基准；同一序列出现冲突容量基准时直接报错。
- 每项代码改动先写失败测试，再写最小实现，再执行对应回归测试。
- 本计划不包含提交、推送和发布动作；这些动作需用户另行明确授权。

---

## Target File Structure

```text
src/chi_generator/
├── domain/
│   ├── models.py          # 请求、校验、时间完整性和输出模型
│   ├── calculations.py    # 电流、DOD、容量和 SoC 纯计算
│   ├── rendering.py       # 仅负责把已确认请求渲染为 CHI 命令
│   ├── validation.py      # 领域错误与风险规则
│   └── service.py         # 领域门面和摘要组装
├── ui/
│   ├── adapters.py        # GuiState -> 领域请求
│   ├── errors.py          # 字段级输入错误
│   ├── main_window.py     # 页面编排、风险确认状态
│   ├── script_output.py   # 脚本预览和复制按钮
│   ├── issue_list.py      # Warning/Error 展示
│   ├── phase_editor.py    # 单工步编辑器
│   ├── loop_editor.py     # 循环块编辑器
│   ├── dialogs.py         # 手动点和循环次数对话框
│   └── widgets.py         # 兼容性 re-export，不再放实现
└── main.py                # 正常启动和 --smoke-test

src/opeis_master/
├── __init__.py
├── app.py                 # 转发 chi_generator.app
├── main.py                # 转发 chi_generator.main
└── gui/main_window.py     # 转发 MainWindow

tests/support/
├── __init__.py
└── factories.py           # 新增合同测试共用的固定请求工厂
```

## Task 1: Freeze the Existing Three-Mode Contract

**Files:**
- Create: `tests/support/__init__.py`
- Create: `tests/support/factories.py`
- Create: `tests/test_three_mode_regression.py`
- Modify: `tests/test_chi_generator_contracts.py`
- Modify: `tests/test_gui_refresh_contracts.py`

**Interfaces:**
- Consumes: `ExperimentSequenceRequest`, `VoltagePointPhase`, `DodPointPhase`, `GuiBackend`。
- Produces: 三种模式在重构期间不可变化的脚本和 UI 合同。

- [ ] **Step 1: Record the current workspace evidence**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Expected: 只出现当前 15 个已跟踪修改；`git diff --check` 返回 0。若文件集合变化，停止实施并先核对新增改动归属。

- [ ] **Step 2: Add deterministic request factories**

`tests/support/factories.py` 完整内容：

```python
from pathlib import Path

from chi_generator.domain.models import (
    BatteryConfig,
    CurrentBasisConfig,
    CurrentBasisMode,
    CurrentInputMode,
    CurrentSetpointConfig,
    DodCapacityBasis,
    DodPointConfig,
    DodPointPhase,
    EisInitStrategy,
    ExperimentPhase,
    ExperimentSequenceRequest,
    ImpedanceConfig,
    ProcessDirection,
    ProjectConfig,
    SamplingConfig,
    ScriptBundle,
    SpacingMode,
    ValidationIssue,
    VoltagePointConfig,
    VoltagePointPhase,
    VoltageWindowConfig,
)


def _base_request(phases: list[ExperimentPhase]) -> ExperimentSequenceRequest:
    return ExperimentSequenceRequest(
        project=ProjectConfig(scheme_name="test", file_prefix="CHI", export_dir=Path(".")),
        battery=BatteryConfig(active_material_mg=1.0, theoretical_capacity_mah_mg=865.0),
        current_basis=CurrentBasisConfig(mode=CurrentBasisMode.MATERIAL),
        impedance_defaults=ImpedanceConfig(
            high_frequency_hz=100000.0,
            low_frequency_hz=1.0,
            amplitude_v=0.005,
            quiet_time_s=2.0,
        ),
        phases=phases,
    )


def _controlled_fields() -> dict[str, object]:
    return {
        "direction": ProcessDirection.DISCHARGE,
        "current_setpoint": CurrentSetpointConfig(mode=CurrentInputMode.RATE, rate_c=0.1),
        "voltage_window": VoltageWindowConfig(upper_v=3.2, lower_v=1.5),
        "sampling": SamplingConfig(pre_wait_s=0.0, sample_interval_s=1.0),
        "insert_eis_after_each_point": True,
    }


def make_voltage_request(strategy: EisInitStrategy) -> ExperimentSequenceRequest:
    phase = VoltagePointPhase(
        label="voltage",
        voltage_points=VoltagePointConfig(spacing_mode=SpacingMode.MANUAL, manual_points_v=[3.0]),
        eis_init_strategy=strategy,
        manual_init_e_v=2.9 if strategy is EisInitStrategy.MANUAL else None,
        **_controlled_fields(),
    )
    return _base_request([phase])


def make_dod_request(
    points: list[float] | None = None,
    *,
    capacity_basis: DodCapacityBasis = DodCapacityBasis.THEORETICAL,
    reference_capacity_mah: float | None = None,
) -> ExperimentSequenceRequest:
    phase = DodPointPhase(
        label="dod",
        dod_points=DodPointConfig(
            dod_points_percent=points if points is not None else [20.0, 40.0],
            capacity_basis=capacity_basis,
            reference_capacity_mah=reference_capacity_mah,
        ),
        post_trigger_rest_s=0.0,
        **_controlled_fields(),
    )
    return _base_request([phase])


def make_sequence_with_dod_capacities(*capacities_mah: float) -> ExperimentSequenceRequest:
    phases = [
        DodPointPhase(
            label=f"dod-{index}",
            dod_points=DodPointConfig(
                dod_points_percent=[20.0],
                capacity_basis=DodCapacityBasis.USER_REFERENCE,
                reference_capacity_mah=capacity,
            ),
            post_trigger_rest_s=0.0,
            **_controlled_fields(),
        )
        for index, capacity in enumerate(capacities_mah, start=1)
    ]
    return _base_request(phases)


def eis_block_after(script: str, save_line: str) -> str:
    return next(block for block in script.split("\n\n") if save_line in block)


def make_bundle(issue: ValidationIssue) -> ScriptBundle:
    return ScriptBundle(issues=[issue])
```

`tests/support/__init__.py` 保持空文件，使测试工厂可以稳定导入。

- [ ] **Step 3: Add explicit three-mode script contracts**

在 `tests/test_three_mode_regression.py` 中建立三个最小请求，分别断言：

```python
def test_target_voltage_peis_uses_target_ei() -> None:
    bundle = ScriptGenerationService().generate(make_voltage_request(EisInitStrategy.TARGET_VOLTAGE))
    assert "tech=cp" in bundle.minimal_script
    assert "ei=3" in bundle.minimal_script
    assert "eio" not in eis_block_after(bundle.minimal_script, "save=CHI_S01_EIS_3V")


def test_relaxed_voltage_eis_uses_eio() -> None:
    bundle = ScriptGenerationService().generate(make_voltage_request(EisInitStrategy.OPEN_CIRCUIT))
    assert "tech=cp" in bundle.minimal_script
    assert "eio" in eis_block_after(bundle.minimal_script, "save=CHI_S01_EIS_3V")


def test_dod_mode_uses_incremental_istep_and_eio() -> None:
    bundle = ScriptGenerationService().generate(make_dod_request([20.0, 40.0]))
    assert bundle.minimal_script.count("tech=istep") == 2
    assert "save=CHI_S01_EIS_DOD20P" in bundle.minimal_script
    assert "eio" in bundle.minimal_script
```

测试从 `tests.support.factories` 导入工厂，不得读取用户磁盘状态。

- [ ] **Step 4: Verify the new tests fail only when behavior drifts**

Run:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python -m pytest tests\test_three_mode_regression.py -v
```

Expected: 当前实现下全部 PASS。若测试因命名细节失败，先按实际纯命令调整断言，不能放宽到只检查“脚本非空”。

- [ ] **Step 5: Run the current baseline suite**

Run:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python -m pytest -q
```

Expected: 0 failed。记录总耗时作为后续测试优化基线；当前参考值约 168 秒。

## Task 2: Make `chi_generator` the Only Business Implementation

**Files:**
- Modify: `src/opeis_master/__init__.py`
- Modify: `src/opeis_master/app.py`
- Modify: `src/opeis_master/main.py`
- Modify: `src/opeis_master/gui/main_window.py`
- Delete after compatibility tests pass: `src/opeis_master/core/`, `domain/`, `models/`, `renderers/`, `ui/`
- Modify: `tests/test_domain_renderer.py`
- Modify: `tests/test_domain_validation.py`
- Modify: `tests/domain/test_service_facade.py`
- Modify: `tests/models/test_configuration_models.py`
- Create: `tests/test_legacy_entrypoints.py`
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: `chi_generator.app.build_application`, `chi_generator.main.main`, `chi_generator.ui.main_window.MainWindow`。
- Produces: 仅保留启动兼容性的 `opeis_master` 包。

- [ ] **Step 1: Write entrypoint compatibility tests**

```python
def test_legacy_main_delegates_to_current_main() -> None:
    from opeis_master.main import main as legacy_main
    from chi_generator.main import main

    assert legacy_main is main


def test_legacy_window_is_current_window() -> None:
    from opeis_master.gui.main_window import MainWindow as LegacyMainWindow
    from chi_generator.ui.main_window import MainWindow

    assert LegacyMainWindow is MainWindow
```

Run:

```powershell
.\.venv\Scripts\python -m pytest tests\test_legacy_entrypoints.py -v
```

Expected before implementation: 至少入口 identity 测试 FAIL。

- [ ] **Step 2: Replace compatibility modules with direct aliases**

`src/opeis_master/main.py` 只保留：

```python
from chi_generator.main import main

__all__ = ["main"]
```

`app.py` 和 `gui/main_window.py` 使用同样的直接导入与 `__all__`，不得再创建第二套 service、validator 或 renderer。

- [ ] **Step 3: Move meaningful old tests to the current API**

把仍有业务价值的旧测试改为导入 `chi_generator.domain`；与现有合同重复的测试删除。迁移后执行：

```powershell
rg -n "opeis_master\.(core|domain|models|renderers|ui)" src tests
```

Expected: 0 matches。

- [ ] **Step 4: Remove unreachable legacy implementations**

只有 Step 3 达到 0 matches 且全量测试通过后，才删除旧目录。随后执行：

```powershell
.\.venv\Scripts\python -m pytest -q
```

Expected: 0 failed；两个命令行入口仍能导入。

- [ ] **Step 5: Correct the architecture document**

`docs/architecture.md` 明确写出：唯一业务源是 `chi_generator`；`opeis_master` 只承诺启动入口兼容，不承诺旧 Python 领域 API。

## Task 3: Correct Capacity, Timeline, and SoC Semantics

**Files:**
- Modify: `src/chi_generator/domain/models.py`
- Modify: `src/chi_generator/domain/calculations.py`
- Modify: `src/chi_generator/domain/rendering.py`
- Modify: `src/chi_generator/domain/validation.py`
- Modify: `src/chi_generator/domain/service.py`
- Create: `tests/test_sequence_timeline_contracts.py`

**Interfaces:**
- Produces: `resolve_sequence_capacity_ah(request) -> float`。
- Produces: `PhaseRenderPlan.start_time_s/end_time_s: float | None`、`timing_complete: bool`。
- Produces: `SequenceScriptBundle.total_wall_clock_s: float | None`、`known_wall_clock_s: float`、`soc_prediction_complete: bool`。

- [ ] **Step 1: Write failing capacity consistency tests**

```python
def test_dod_reference_capacity_drives_sequence_soc_capacity() -> None:
    request = make_dod_request(capacity_basis=DodCapacityBasis.USER_REFERENCE, reference_capacity_mah=2.0)
    assert resolve_sequence_capacity_ah(request) == pytest.approx(0.002)


def test_conflicting_dod_capacities_are_rejected() -> None:
    request = make_sequence_with_dod_capacities(2.0, 2.5)
    result = validate_sequence_request(request)
    assert [issue.code for issue in result.errors] == ["inconsistent_dod_capacity_basis"]
```

Expected before implementation: import or assertion FAIL。

- [ ] **Step 2: Implement one sequence capacity resolver**

在 `calculations.py` 新增：

```python
def resolve_sequence_capacity_ah(request: ExperimentSequenceRequest) -> float:
    dod_capacities = [
        resolve_dod_capacity_mah(request.battery, phase.dod_points) / 1000.0
        for phase in request.phases
        if isinstance(phase, DodPointPhase)
    ]
    if dod_capacities:
        first = dod_capacities[0]
        if any(not isclose(value, first, rel_tol=1e-9, abs_tol=1e-12) for value in dod_capacities[1:]):
            raise ValueError("all DOD phases must use the same capacity")
        return first
    for phase in request.phases:
        if isinstance(phase, ControlledPhaseBase):
            return resolve_current(request.battery, request.current_basis, phase.current_setpoint).one_c_current_a
    return 0.0
```

`validation.py` 将该 `ValueError` 转为 code=`inconsistent_dod_capacity_basis` 的 blocking error。`rendering.py` 和 SoC 仿真只调用该函数，不再使用 `one_c_current_a or 0.0` 作为另一套容量来源。

- [ ] **Step 3: Write failing unknown-CP-time tests**

```python
def test_voltage_cp_does_not_claim_exact_total_time_or_soc() -> None:
    bundle = ScriptGenerationService().generate(make_voltage_request(EisInitStrategy.TARGET_VOLTAGE))
    assert bundle.total_wall_clock_s is None
    assert bundle.known_wall_clock_s > 0
    assert bundle.soc_prediction_complete is False
    assert bundle.phase_plans[0].timing_complete is False
    assert bundle.phase_plans[0].start_time_s is not None
    assert bundle.phase_plans[0].end_time_s is None
```

- [ ] **Step 4: Represent unknown timing explicitly**

修改模型默认值：

```python
class PhaseRenderPlan(DomainModel):
    start_time_s: float | None = None
    end_time_s: float | None = None
    wall_clock_total_s: float | None = None
    known_wall_clock_s: float = 0.0
    timing_complete: bool = True


class SequenceScriptBundle(ScriptBundle):
    total_wall_clock_s: float | None = None
    known_wall_clock_s: float = 0.0
    soc_prediction_complete: bool = True
```

电压 CP 工步渲染命令不变，但计划层设置 `timing_complete=False`。CP 后的绝对 marker、start、end 不再生成；固定静置和 EIS 时长只累计到 `known_wall_clock_s`。UI 摘要显示“已知固定时长至少 X min，CP 到目标电压耗时未知”。

- [ ] **Step 5: Stop treating EIS as continued constant current**

所有 `simulation_steps.append((eis_duration_s, signed_current_a))` 改为 `(eis_duration_s, 0.0)`。等效容量补偿继续在 `plan_time_points()` 内独立计算，摘要字段由 `total_eis_loss_mah` 改名为 `total_interruption_equivalent_mah`，避免把“未继续恒流的等效差值”写成真实 EIS 容量损失。

- [ ] **Step 6: Verify the domain slice**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests\test_sequence_timeline_contracts.py tests\test_chi_generator_contracts.py tests\test_validation_risk_and_basis_contracts.py -q
```

Expected: 0 failed。

## Task 4: Simplify Impedance Rendering and Validation

**Files:**
- Modify: `src/chi_generator/domain/models.py`
- Modify: `src/chi_generator/domain/rendering.py`
- Modify: `src/chi_generator/domain/validation.py`
- Modify: `tests/test_three_mode_regression.py`
- Modify: `tests/test_core_renderer_contracts.py`

**Interfaces:**
- Consumes: `EisInitStrategy`。
- Produces: `_render_impedance(..., init_strategy, init_e_v)`，不再接收无效 `force_potentiostatic`。

- [ ] **Step 1: Add a pure-command test**

```python
def test_minimal_script_contains_only_chi_commands() -> None:
    script = ScriptGenerationService().generate(make_dod_request([20.0, 40.0])).minimal_script
    assert "TODO" not in script
    assert "#" not in script
    assert "=" in script
    assert all(not line.startswith(("说明", "公式", "warning")) for line in script.splitlines())
```

- [ ] **Step 2: Remove the unused potentiostatic flag**

将 `_render_impedance` 改为：

```python
def _render_impedance(
    impedance: ImpedanceConfig,
    *,
    save_name: str,
    init_strategy: EisInitStrategy = EisInitStrategy.OPEN_CIRCUIT,
    init_e_v: float | None = None,
) -> list[str]:
    if init_strategy is EisInitStrategy.OPEN_CIRCUIT:
        init_line = "eio"
    else:
        if init_e_v is None:
            raise ValueError("explicit EIS initial voltage is required")
        init_line = f"ei={format_number(init_e_v)}"
```

目标电压和手动模式传明确 `init_e_v`；OCV 和 DOD 传 `OPEN_CIRCUIT`。不新增 GEIS，因为当前需求和模型都只支持 potentiostatic EIS。

- [ ] **Step 3: Align validation with rendering**

验证层必须在进入 renderer 前阻止：手动模式缺少电位、目标电位越界、DOD 非 OCV 初始策略。renderer 遇到非法状态直接抛错，不添加默认 `0.0 V`。

- [ ] **Step 4: Run rendering contracts**

Run:

```powershell
.\.venv\Scripts\python -m pytest tests\test_three_mode_regression.py tests\test_core_renderer_contracts.py tests\test_domain_renderer.py -q
```

Expected: 0 failed；生成脚本中没有公式和占位注释。

## Task 5: Add Explicit High-Risk Confirmation and Field Errors

**Files:**
- Modify: `src/chi_generator/domain/models.py`
- Create: `src/chi_generator/ui/errors.py`
- Modify: `src/chi_generator/ui/parsers.py`
- Modify: `src/chi_generator/ui/adapters.py`
- Modify: `src/chi_generator/ui/main_window.py`
- Modify: `src/chi_generator/ui/script_output.py`
- Create: `tests/test_risk_confirmation_contracts.py`

**Interfaces:**
- Produces: `ScriptBundle.requires_confirmation: bool`。
- Produces: `GuiFieldError(field: str, message: str)`。
- MainWindow 保存当前风险 fingerprint；任一输入变化后自动失效。

- [ ] **Step 1: Add risk classification tests**

```python
def test_high_risk_warning_requires_confirmation() -> None:
    bundle = make_bundle(ValidationIssue(
        severity=Severity.WARNING,
        code="dense_eis_low_frequency",
        message="dense",
        risk_level=RiskLevel.HIGH,
    ))
    assert bundle.can_generate is True
    assert bundle.requires_confirmation is True


def test_medium_warning_does_not_require_confirmation() -> None:
    bundle = make_bundle(ValidationIssue(
        severity=Severity.WARNING,
        code="rest_dominates_sequence",
        message="rest",
        risk_level=RiskLevel.MEDIUM,
    ))
    assert bundle.requires_confirmation is False
```

- [ ] **Step 2: Add the domain property**

```python
@property
def requires_confirmation(self) -> bool:
    return any(
        issue.severity is Severity.WARNING and issue.risk_level is RiskLevel.HIGH
        for issue in self.issues
    )
```

Error 仍由 `can_generate=False` 阻断；高风险 Warning 不伪装成 Error。

- [ ] **Step 3: Add field-aware parsing errors**

`errors.py`：

```python
class GuiFieldError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message
```

`parse_float`、`parse_int` 接收稳定字段 key 和中文 label；`GuiBackend` 把 pydantic 的首个 `loc` 转为 `GuiFieldError`。不得在 `refresh_preview()` 中把所有问题统一改成 `ui.refresh`。

- [ ] **Step 4: Implement confirmation state in MainWindow**

风险 fingerprint 使用不可变元组：

```python
def _risk_fingerprint(bundle: ScriptBundle) -> tuple[tuple[str, str | None, str], ...]:
    return tuple(
        (issue.code, issue.field, issue.message)
        for issue in bundle.issues
        if issue.severity is Severity.WARNING and issue.risk_level is RiskLevel.HIGH
    )
```

`schedule_refresh()` 清除已确认 fingerprint。只有 `bundle.can_generate` 且不存在未确认高风险时，`ScriptOutputPanel` 才启用复制按钮。确认按钮文字固定为“我已确认高风险，允许复制”。

- [ ] **Step 5: Verify UI behavior**

Run:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python -m pytest tests\test_risk_confirmation_contracts.py tests\test_gui_refresh_contracts.py -q
```

Expected: Error 不能复制；高风险 Warning 确认前不能复制、确认后可以；修改任一输入后再次不能复制；字段错误显示具体字段。

## Task 6: Split the Oversized UI Module and Remove Runtime Patches

**Files:**
- Create: `src/chi_generator/ui/script_output.py`
- Create: `src/chi_generator/ui/issue_list.py`
- Create: `src/chi_generator/ui/dialogs.py`
- Create: `src/chi_generator/ui/phase_editor.py`
- Create: `src/chi_generator/ui/loop_editor.py`
- Replace: `src/chi_generator/ui/widgets.py` with re-exports
- Modify: `src/chi_generator/ui/main_window.py`
- Modify: `tests/test_gui_layout_contracts.py`
- Modify: `tests/test_gui_refresh_contracts.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Existing imports from `chi_generator.ui.widgets` remain valid through re-export。
- 每个类只定义一次，不在模块导入时替换类方法。

- [ ] **Step 1: Add structural tests**

```python
def test_widgets_module_only_reexports_public_widgets() -> None:
    source = Path("src/chi_generator/ui/widgets.py").read_text(encoding="utf-8")
    assert "_ORIGINAL_" not in source
    assert ".__init__ =" not in source
    assert source.count("class IssueListWidget") == 0


def test_production_window_defines_tested_helpers() -> None:
    assert hasattr(MainWindow, "_manual_refresh")
    assert hasattr(MainWindow, "_readonly_line_edit")
```

- [ ] **Step 2: Move classes without behavior changes**

移动顺序：公共小控件和 ScriptOutputPanel → IssueListWidget → dialogs → WorkstepEditorRow → LoopBlockWidget。每移动一类，执行对应 GUI 测试，避免一次性重写 1400 行文件。

- [ ] **Step 3: Remove duplicate definitions**

只保留 `GuidedManualPointDialog` 版本的时间/电压编辑方法；删除前面的同名 `_edit_manual_time_points`、`_edit_manual_voltage_points`。`IssueListWidget`、`GuidedManualPointDialog` 各只定义一次。

- [ ] **Step 4: Remove runtime monkey-patches**

删除所有 `_ORIGINAL_*`、`Class.method = replacement`。清理文案的方法成为类内私有方法，在 `__init__`、`set_state()` 和可见性变化后直接调用。

- [ ] **Step 5: Remove test monkey-patching**

删除 `tests/conftest.py::_compat_manual_refresh`。测试需要的方法在 `MainWindow` 正式实现：

```python
def _manual_refresh(self) -> None:
    self._refresh_timer.stop()
    self.refresh_preview()
```

只读行编辑器也成为正式静态辅助方法，不再由测试注入。

- [ ] **Step 6: Align voltage spacing capability**

当前产品只使用范围线性生成和手动列表。删除未被 UI、文档或测试使用的 `SpacingMode.LOG`、`SpacingMode.SQRT` 分支，保留 `LINEAR`、`MANUAL`，避免领域层暴露无法从 GUI 配置的功能。

- [ ] **Step 7: Run GUI tests**

Run:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python -m pytest tests\test_gui_layout_contracts.py tests\test_gui_refresh_contracts.py tests\test_gui_smoke.py -q
```

Expected: 0 failed，且 `rg -n "_ORIGINAL_|__init__ =|def _edit_manual_time_points" src\chi_generator\ui` 只返回一个 `_edit_manual_time_points` 定义。

## Task 7: Make Tests Fast and Enforce Quality Gates

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/conftest.py`
- Create: `tests/test_legacy_entrypoints.py`
- Create: `.github/workflows/test.yml`
- Modify: `docs/testing.md`

**Interfaces:**
- Produces: `domain`、`gui`、`packaging` 三类明确 marker。
- Produces: Windows/Python 3.11 自动测试门禁。

- [ ] **Step 1: Classify the suite**

为真正实例化窗口的测试添加 `@pytest.mark.gui`；纯 adapter、preset migration 和领域测试不得创建 MainWindow。把能通过 `GuiBackend` 验证的测试从 GUI 文件迁出。

- [ ] **Step 2: Add coverage support**

`pyproject.toml` 的 dev 依赖加入 `pytest-cov>=6,<7`，并增加：

```toml
[tool.coverage.run]
source = ["chi_generator"]
branch = true

[tool.coverage.report]
fail_under = 80
show_missing = true
```

- [ ] **Step 3: Add Windows CI**

工作流固定：checkout → Python 3.11 → `pip install -e .[dev]` → 设置 `QT_QPA_PLATFORM=offscreen` → `pytest --cov=chi_generator --cov-report=term-missing`。

- [ ] **Step 4: Verify speed and coverage**

Run:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
Measure-Command { .\.venv\Scripts\python -m pytest -m "not gui" -q }
Measure-Command { .\.venv\Scripts\python -m pytest -q }
.\.venv\Scripts\python -m pytest --cov=chi_generator --cov-report=term-missing -q
```

Expected: 0 failed；非 GUI 测试目标小于 15 秒；全量测试目标小于 90 秒；branch coverage 不低于 80%。如果未达目标，报告具体慢测试，不能通过放宽超时掩盖。

## Task 8: Make Packaging Reproducible and Self-Verifying

**Files:**
- Create: `scripts/build_release.ps1`
- Replace: `build.bat` with a thin wrapper
- Modify: `CHI-OPEIS.spec`
- Modify: `src/chi_generator/main.py`
- Create: `tests/test_packaged_entrypoint.py`
- Modify: `tests/test_packaging_docs.py`
- Modify: `docs/packaging.md`

**Interfaces:**
- Produces: `chi_generator.main.main(argv: Sequence[str] | None = None) -> int`。
- Produces: `CHI-OPEIS.exe --smoke-test` 返回 0。
- Produces: versioned zip 和 `SHA256SUMS.txt`。

- [ ] **Step 1: Add a non-interactive packaged smoke mode**

`main.py` 支持：

```python
def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv or [])
    app, window = build_application()
    if "--smoke-test" in args:
        window.refresh_preview()
        window.close()
        app.processEvents()
        return 0
    window.show()
    return app.exec()
```

模块直接执行时传入 `sys.argv[1:]`。测试断言 `main(["--smoke-test"]) == 0`。

- [ ] **Step 2: Replace activation-dependent build logic**

`scripts/build_release.ps1` 必须直接调用 `.venv\Scripts\python.exe`，并在删除前验证 `build`、`dist` 的解析路径都位于项目根目录内。步骤固定为：环境检查 → 清理 → 全量测试 → `python -m PyInstaller` → 检查 EXE → `--smoke-test` → 压缩 → SHA256。

任一步 `$LASTEXITCODE -ne 0` 立即 `throw`，不得继续生成看似成功的 zip。

- [ ] **Step 3: Make build.bat a wrapper**

```bat
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_release.ps1"
exit /b %ERRORLEVEL%
```

- [ ] **Step 4: Verify PyInstaller contents**

`CHI-OPEIS.spec` 保留实际需要的 `QtCharts`、Windows platform、SVG、JPEG、TIFF、WebP 和 Schannel 插件。删除 `opeis_master` 业务模块后继续明确 exclude。检查 PyInstaller warning 文件，不允许存在 `chi_generator`、PySide6 QtCharts 或 pydantic 的 missing import。

- [ ] **Step 5: Run release build verification**

Run:

```powershell
.\build.bat
Get-ChildItem dist\CHI-OPEIS\CHI-OPEIS.exe, dist\CHI-OPEIS-*-windows-x64.zip, dist\SHA256SUMS.txt
& dist\CHI-OPEIS\CHI-OPEIS.exe --smoke-test
```

Expected: 构建脚本返回 0；三个产物存在；EXE smoke test 返回 0；SHA256 文件中的哈希与 `Get-FileHash` 一致。

## Task 9: Synchronize Documentation and Final Acceptance

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/domain.md`
- Modify: `docs/usage.md`
- Modify: `docs/testing.md`
- Modify: `docs/packaging.md`
- Modify: `docs/examples.md`
- Modify: `pyproject.toml`

**Interfaces:**
- 文档名称、脚本行为、版本和发布产物必须来自当前代码和构建结果。

- [ ] **Step 1: Update the three-mode user contract**

文档分别说明：

- 目标电压 PEIS：CP 触发后 `ei=目标电压`。
- 电压弛豫 EIS：电压只作为 CP 触发条件，静置后使用 `eio`。
- DOD 准原位 EIS：容量百分比换算恒流时间，静置后使用 `eio`。
- 电压 CP 总时长未知，因此总历时和 SoC 可能显示“不完整”。
- 高风险 Warning 必须确认后才能复制脚本。

- [ ] **Step 2: Remove stale generated facts from README**

README 不再硬编码某次本地构建 SHA256。改为要求随发布包读取 `SHA256SUMS.txt`。测试数量不手写固定数字，`docs/testing.md` 只写执行命令、范围和最近验证日期。

- [ ] **Step 3: Set one release version**

三种新模式和全局优化完成后，将 `pyproject.toml` 版本提升到一个未被现有 `v0.2.0` 标签占用的新版本；README 包名和 PowerShell 构建脚本从该版本生成，不在多处手工复制版本号。

- [ ] **Step 4: Run final acceptance**

Run:

```powershell
git diff --check
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python -m pytest --cov=chi_generator --cov-report=term-missing -q
.\build.bat
& dist\CHI-OPEIS\CHI-OPEIS.exe --smoke-test
rg -n "59 个测试|1ED44979|backend is not connected|TODO: implement PEIS" README.md docs src
git status --short
```

Expected:

- `git diff --check` 返回 0。
- 测试 0 failed，覆盖率达到门禁。
- 构建和 EXE smoke test 返回 0。
- 过时测试数、旧哈希、占位后端和未完成 PEIS 文案 0 matches。
- `git status` 只包含本计划明确列出的修改，不包含意外生成文件。

## Review Gates

每个 Task 完成后执行两次检查：

1. Review 查 Bug：检查命令语义、类型、边界条件、用户已有改动和测试证据。
2. 第一性原理分析：确认改动是否解决真实问题，是否引入了可以删除的状态、分支、兼容层或估算。

只有前一 Task 验收通过才能进入下一 Task。Task 3、Task 5 和 Task 8 是发布阻断项；任一未完成，不得生成正式发布包。
