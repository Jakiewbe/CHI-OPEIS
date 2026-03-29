# 架构说明

## 主线

- `chi_generator` 是当前主实现
- `opeis_master` 是兼容层
- 桌面应用通过 `chi_generator.app.build_application()` 装配

## 分层

### UI 层

位置：`src/chi_generator/ui/`

职责：

- 组织 PyQt6 界面
- 收集输入
- 展示脚本预览、摘要、告警和错误
- 根据校验结果做字段高亮和按钮禁用

UI 不负责：

- 电流换算
- 取点规划
- CHI 脚本渲染

### Domain 层

位置：`src/chi_generator/domain/`

职责：

- pydantic 模型
- 电流与倍率换算
- 电压点/时间点/分段时间点规划
- Warning / Error 校验
- CHI Macro Command 纯文本渲染

### 兼容层

位置：`src/opeis_master/`

职责：

- 保留旧入口路径
- 转发到新的 GUI 实现
- 保留旧 domain 契约测试使用的模块

## 设计约束

- 公式不能进入最终脚本
- 最终脚本只输出 CHI 命令和数字
- `Error` 阻止生成
- `Warning` 允许继续，但必须醒目展示
