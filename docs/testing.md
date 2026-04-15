# 测试说明

## 运行方式

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\pytest -q
```

## 当前覆盖

共计 **59 个测试**，全部通过。覆盖范围：

### Domain 层
- 电流换算（material / reference basis）
- 时间点展开（segmented / fixed / manual 模式）
- 电压点展开（linear / log / sqrt / manual 间距）
- 中断补偿与 CTC 等效容量补偿
- SoC 轨迹模拟与耗尽检测
- CTC 推荐取点规划

### 渲染层
- Sequence 脚本渲染（istep / cp / imp / delay）
- Pulse 脚本渲染（pre/post EIS 唯一命名）
- 通用头尾、OCV 初始 EIS
- 保存名分配器（冲突避免）

### 校验层
- 低频密集 EIS 告警（high risk）
- 中断进度告警
- 频繁充放电切换告警
- SoC 耗尽风险
- CTC 容量补偿提示
- 充电 CP→PEIS 过渡提示
- 手动电压点单调性校验

### GUI 层
- 离屏主窗口实例化
- 左/右面板布局约束
- 工步编辑器增删移
- 循环块（loop block）
- 工作区模式切换（sequence / pulse）
- 脉冲松弛字段
- 采样间隔预设刷新
- 固定模式支持 duration + count 规划
- 手动模式与补偿摘要
- 智能推荐取点
- 工步名回退
- 预设文件往返（含旧预设降级加载）

### 打包文档
- packaging.md 依赖与运行时说明

### 兼容层
- `opeis_master` 旧契约测试
