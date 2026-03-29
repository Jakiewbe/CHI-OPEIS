# 辰华原位阻抗脚本生成终端

本项目是一个本地 `PyQt6` 桌面应用，用于把 CHI 原位阻抗实验参数整理成可直接复制到 `CHI Macro Command` 的纯命令脚本。

当前版本重点解决三类问题：

- 用工步序列编辑器配置 `固定时间点`、`固定电压点`、`静置` 的交替流程
- 用独立 `Pulse` 页面配置恢复段与脉冲段
- 在生成前集中展示 `Warnings / Errors`，避免把不合理参数直接带进实验

## 主要能力

- 工步序列支持充电、放电、静置交替排列
- 固定时间点采用三段式输入：前期、平台期、后期
- 固定电压点采用区间输入：起点、终点、步长
- 每个工步可单独控制是否在取点后插入 EIS
- 支持中断补偿时间模式
- 右侧实时显示摘要、告警和极简脚本预览
- 支持整体工作流预设文件：`.chi-preset`
- 支持打包为无需 Python 的 Windows EXE

## 技术栈

- Python 3.11+
- PyQt6
- pydantic
- pytest
- PyInstaller

## 本地运行

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev,build]
.\.venv\Scripts\python -m chi_generator.main
```

兼容入口：

```powershell
.\.venv\Scripts\python -m opeis_master.main
```

## 测试

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python -m pytest -q
```

## 打包

```powershell
.\.venv\Scripts\pyinstaller --noconfirm CHI-OPEIS.spec
```

打包结果默认在：

```text
dist/CHI-OPEIS/
```

分发时需要拷走整个 `dist/CHI-OPEIS/` 目录，不能只拿 `exe` 单文件。

## 目录结构

```text
src/chi_generator/domain/    领域模型、校验、渲染、脚本生成
src/chi_generator/ui/        PyQt6 界面与 GUI -> Domain 适配
src/chi_generator/app.py     应用装配入口
src/opeis_master/            兼容层与旧导入路径
tests/                       GUI、domain、兼容合同测试
docs/                        架构、测试、打包说明
```

## 关键约束

- UI 逻辑与 domain 逻辑保持分离
- 最终 CHI 脚本只输出纯命令，不输出公式
- 有 `Error` 时不允许生成与复制
- `Warning` 会在界面右侧显著展示
- 默认脚本需要能直接复制到 CHI Macro Command

## 许可证

当前仓库未单独声明许可证；如需开源发布，请补充 `LICENSE` 文件。
