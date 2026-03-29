from __future__ import annotations

from opeis_master.core.service import ScriptGenerationService
from opeis_master.gui.main_window import MainWindow


def test_main_window_smoke(qt_app) -> None:
    window = MainWindow(ScriptGenerationService())

    assert window.windowTitle()
    assert window._scenario.currentData() == "sequence"
    window.close()
