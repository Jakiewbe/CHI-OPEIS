from __future__ import annotations

from pathlib import Path


def test_packaging_notes_cover_blank_pc_runtime_and_build_dependencies() -> None:
    text = Path("docs/packaging.md").read_text(encoding="utf-8")

    assert "Python 3.11" in text
    assert "PySide6" in text
    assert "pydantic" in text
    assert "pytest" in text
    assert "pytest-qt" in text
    assert "PyInstaller" in text
    assert "pip install -e .[build]" in text
    assert "pip install -e .[dev,build]" in text
    assert "Microsoft Visual C++ Redistributable 2015-2022" in text
    assert "dist/CHI-OPEIS/" in text
