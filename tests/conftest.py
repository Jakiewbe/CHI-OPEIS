from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _force_offscreen_qt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qt_app():
    pytest.importorskip("PySide6")

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
