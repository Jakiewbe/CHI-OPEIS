from pathlib import Path

from chi_generator.domain.models import SpacingMode


def test_widgets_have_single_definitions_and_no_runtime_patches() -> None:
    source = Path("src/chi_generator/ui/widgets.py").read_text(encoding="utf-8")

    assert "_ORIGINAL_" not in source
    assert ".__init__ =" not in source
    assert "class IssueListWidget" not in source
    assert "class ScriptOutputPanel" not in source
    assert source.count("class GuidedManualPointDialog") == 1
    assert source.count("def _edit_manual_time_points") == 1
    assert source.count("def _edit_manual_voltage_points") == 1

    assert "class IssueListWidget" in Path("src/chi_generator/ui/issue_list.py").read_text(encoding="utf-8")
    assert "class ScriptOutputPanel" in Path("src/chi_generator/ui/script_output.py").read_text(encoding="utf-8")


def test_conftest_does_not_patch_production_ui() -> None:
    source = Path("tests/conftest.py").read_text(encoding="utf-8")

    assert "monkeypatch" not in source
    assert "_manual_refresh" not in source
    assert "_readonly_line_edit" not in source


def test_voltage_spacing_matches_the_two_ui_modes() -> None:
    assert {mode.value for mode in SpacingMode} == {"linear", "manual"}
