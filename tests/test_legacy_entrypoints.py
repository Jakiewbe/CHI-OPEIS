from chi_generator.app import build_application
from chi_generator.main import main
from chi_generator.ui.main_window import MainWindow
from opeis_master.app import build_application as legacy_build_application
from opeis_master.gui.main_window import MainWindow as LegacyMainWindow
from opeis_master.main import main as legacy_main


def test_legacy_main_delegates_to_current_main() -> None:
    assert legacy_main is main


def test_legacy_app_delegates_to_current_app() -> None:
    assert legacy_build_application is build_application


def test_legacy_window_is_current_window() -> None:
    assert LegacyMainWindow is MainWindow
