"""Application assembly for the CHI generator."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from chi_generator.domain.service import ScriptGenerationService
from chi_generator.ui.main_window import MainWindow


def build_application() -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication([])
    service = ScriptGenerationService()
    window = MainWindow(service)
    return app, window
