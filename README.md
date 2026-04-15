# OPEIS Master — 辰华原位阻抗脚本生成终端

一个本地 PySide6 桌面应用，将 CHI 原位阻抗（EIS）实验参数整理为可直接粘贴到 **CHI Macro Command** 的纯命令脚本。

## 适用场景

在辰华电化学工作站上执行原位阻抗实验时，手动编写 Macro Command 脚本繁琐且容易出错。本工具通过图形界面引导完成实验参数配置，自动生成可执行的纯命令脚本。

## 核心功能

- **工步序列编辑** — 配置充电（固定时间点 / 固定电压点）、放电、静置的交替流程
- **Pulse 页面** — 独立配置恢复段与脉冲段参数
- **三段式时间输入** — 固定时间点分为前期、平台期、后期
- **区间电压输入** — 固定电压点支持起点、终点、步长
- **逐工步 EIS 控制** — 每个工步可单独控制是否在取点后插入 EIS
- **中断补偿时间模式** — 支持实验中断路后自动补偿
- **实时校验** — 生成前集中展示 Warnings / Errors，阻止不合理参数进入实验
- **工作流预设** — 支持保存和加载 `.chi-preset` 文件
- **一键打包** — 可打包为无需 Python 环境的 Windows EXE 分发

## 技术栈

| 组件 | 依赖 |
|------|------|
| 运行环境 | Python 3.11+ |
| GUI 框架 | PySide6, PySide6-Fluent-Widgets |
| 数据校验 | pydantic |
| 测试 | pytest, pytest-qt |
| 打包 | PyInstaller |

## 快速开始

### 安装与运行

```powershell
# 创建虚拟环境
py -3.11 -m venv .venv

# 激活并安装依赖
.\.venv\Scripts\python -m pip install -e .[dev,build]

# 启动应用
.\.venv\Scripts\python -m chi_generator.main
```

### 运行测试

```powershell
$env:QT_QPA_PLATFORM="offscreen"
.\.venv\Scripts\python -m pytest -q
```

### 打包分发

```powershell
.\.venv\Scripts\pyinstaller --noconfirm CHI-OPEIS.spec
```

打包输出位于 `dist/CHI-OPEIS/`，分发时需拷贝整个目录（不能只复制 `.exe` 文件）。

## 项目结构

```
src/chi_generator/
├── domain/          领域模型、校验、渲染、脚本生成
├── services/        预设管理、脚本生成服务
├── ui/              PySide6 界面组件与 Domain 适配
├── app.py           应用装配入口
└── main.py          程序入口
src/opeis_master/    兼容层与旧导入路径
tests/               合同测试、GUI 测试、Domain 测试
docs/                架构、测试、打包说明
```

## 设计原则

- **关注点分离** — UI 逻辑与 Domain 逻辑严格隔离
- **纯命令输出** — 最终 CHI 脚本仅输出命令，不包含公式
- **校验前置** — 存在 Error 时禁止生成与复制，Warning 在界面显著展示
- **即拷即用** — 生成的脚本可直接粘贴到 CHI Macro Command 执行

## 许可证

本项目基于 MIT 许可证开源。详见 [LICENSE](LICENSE) 文件。
