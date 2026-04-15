# EXE 打包说明

## 运行环境

- Windows 10/11 x64
- Python 3.11+
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

推荐使用 spec 文件构建：

```powershell
.\.venv\Scripts\pyinstaller --noconfirm CHI-OPEIS.spec
```

等效的 CLI 命令（仅用于理解 spec 的行为）：

```powershell
.\.venv\Scripts\pyinstaller --noconfirm --windowed ^
  --name CHI-OPEIS --paths src ^
  --collect-submodules chi_generator ^
  --exclude-module opeis_master ^
  --exclude-module setuptools ^
  --exclude-module pip ^
  src/chi_generator/main.py
```

## 一键构建

```powershell
.\build.bat
```

该脚本会依次执行：清理旧产物 → 运行测试 → PyInstaller 构建 → 生成 release zip。

默认产物目录：

```text
dist/CHI-OPEIS/
dist/CHI-OPEIS-release.zip
```

## 空白电脑分发

如果目标电脑没有 Python，只分发 PyInstaller 产物即可。建议同时准备：

- `dist/CHI-OPEIS/` 整个目录
- `Microsoft Visual C++ Redistributable 2015-2022` x64

如果目标电脑需要直接运行源码，还需要额外安装：

- Python 3.11+
- `PySide6`
- `PySide6-Fluent-Widgets`
- `pydantic`

## 备注

- 生成脚本不依赖目标电脑上的 Python 运行环境。
- 如果后续调整入口文件位置，需要同步更新 `CHI-OPEIS.spec` 中的 `src/chi_generator/main.py`。
