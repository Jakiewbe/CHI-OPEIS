# EXE 打包说明

## 运行环境

- Windows 10/11 x64
- Python 3.11.x
- `PySide6`
- `PySide6-Fluent-Widgets`
- `pydantic`
- `pytest`
- `pytest-qt`
- `PyInstaller`

## 开发安装

如果你要运行源码并执行回归测试：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev,build]
```

如果你只需要构建 `exe`：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -e .[build]
```

## 打包命令

在仓库根目录执行：

```powershell
.\.venv\Scripts\pyinstaller --noconfirm --windowed --name CHI-OPEIS --paths src --collect-submodules chi_generator --collect-submodules opeis_master src/chi_generator/main.py
```

默认产物目录：

```text
dist/CHI-OPEIS/
```

## 空白电脑分发

如果目标电脑没有 Python，只分发 PyInstaller 产物即可。建议同时准备：

- `dist/CHI-OPEIS/` 整个目录
- `Microsoft Visual C++ Redistributable 2015-2022` x64

如果目标电脑需要直接运行源码，还需要额外安装：

- Python 3.11.x
- `PySide6`
- `PySide6-Fluent-Widgets`
- `pydantic`

## 备注

- 生成脚本不依赖目标电脑上的 Python 运行环境。
- 如果后续调整入口文件位置，需要同步更新 PyInstaller 命令中的 `src/chi_generator/main.py`。
