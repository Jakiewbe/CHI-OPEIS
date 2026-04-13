from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _force_offscreen_qt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def _compat_manual_refresh(monkeypatch) -> None:
    from PySide6.QtWidgets import QLineEdit
    from chi_generator.ui.main_window import MainWindow

    if not hasattr(MainWindow, "_manual_refresh"):
        monkeypatch.setattr(MainWindow, "_manual_refresh", lambda self: self.refresh_preview(), raising=False)
    if not hasattr(MainWindow, "_readonly_line_edit"):
        def _readonly_line_edit(self, text: str):
            edit = QLineEdit(text, self)
            edit.setReadOnly(True)
            return edit

        monkeypatch.setattr(MainWindow, "_readonly_line_edit", _readonly_line_edit, raising=False)


@pytest.fixture(scope="session")
def qt_app():
    pytest.importorskip("PySide6")

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
