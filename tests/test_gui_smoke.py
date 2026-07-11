from __future__ import annotations

import pytest

from chi_generator.domain.service import ScriptGenerationService
from chi_generator.ui.main_window import MainWindow

pytestmark = pytest.mark.gui


def test_main_window_smoke(qt_app) -> None:
    window = MainWindow(ScriptGenerationService())

    assert window.windowTitle()
    assert window._scenario.currentData() == "sequence"
    window.close()
