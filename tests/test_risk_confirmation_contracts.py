from importlib import import_module

import pytest

from chi_generator.domain.models import RiskLevel, Severity, ValidationIssue
from chi_generator.ui.adapters import GuiBackend
from chi_generator.ui.main_window import MainWindow
from chi_generator.ui.models import GuiState
from tests.support.factories import make_bundle

pytestmark = pytest.mark.gui


def test_high_risk_warning_requires_confirmation() -> None:
    bundle = make_bundle(
        ValidationIssue(
            severity=Severity.WARNING,
            code="dense_eis_low_frequency",
            message="dense",
            risk_level=RiskLevel.HIGH,
        )
    )

    assert bundle.can_generate is True
    assert bundle.requires_confirmation is True


def test_medium_warning_does_not_require_confirmation() -> None:
    bundle = make_bundle(
        ValidationIssue(
            severity=Severity.WARNING,
            code="rest_dominates_sequence",
            message="rest",
            risk_level=RiskLevel.MEDIUM,
        )
    )

    assert bundle.requires_confirmation is False


def test_invalid_gui_number_reports_the_input_field() -> None:
    errors_module = import_module("chi_generator.ui.errors")
    error_type = getattr(errors_module, "GuiFieldError")
    state = GuiState(active_material_mg="not-a-number")

    with pytest.raises(error_type) as captured:
        GuiBackend().preview(state)

    assert captured.value.field == "活性物质量"
    assert "合法数字" in captured.value.message


def test_high_risk_copy_requires_current_confirmation(qt_app) -> None:
    window = MainWindow()
    window.refresh_preview()

    assert window.output_panel.confirm_risk_button.isVisibleTo(window.output_panel)
    assert window.output_panel.copy_minimal_button.isEnabled() is False

    window.output_panel.confirm_risk_button.click()

    assert window.output_panel.copy_minimal_button.isEnabled() is True
    window.schedule_refresh()
    window.refresh_preview()
    assert window.output_panel.copy_minimal_button.isEnabled() is False
    window.close()
