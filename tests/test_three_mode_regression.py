import inspect

from chi_generator.domain.models import EisInitStrategy
from chi_generator.domain.rendering import _render_impedance
from chi_generator.domain.service import ScriptGenerationService
from tests.support.factories import eis_block_after, make_dod_request, make_voltage_request


def test_target_voltage_peis_uses_target_ei() -> None:
    bundle = ScriptGenerationService().generate(make_voltage_request(EisInitStrategy.TARGET_VOLTAGE))

    assert "tech=cp" in bundle.minimal_script
    assert "ei=3" in bundle.minimal_script
    assert "eio" not in eis_block_after(bundle.minimal_script, "save=CHI_S01_EIS_3p00V")


def test_relaxed_voltage_eis_uses_eio() -> None:
    bundle = ScriptGenerationService().generate(make_voltage_request(EisInitStrategy.OPEN_CIRCUIT))

    assert "tech=cp" in bundle.minimal_script
    assert "eio" in eis_block_after(bundle.minimal_script, "save=CHI_S01_EIS_3p00V")


def test_dod_mode_uses_incremental_istep_and_eio() -> None:
    bundle = ScriptGenerationService().generate(make_dod_request([20.0, 40.0]))

    assert bundle.minimal_script.count("tech=istep") == 2
    assert "save=CHI_S01_EIS_DOD20P" in bundle.minimal_script
    assert "eio" in bundle.minimal_script


def test_impedance_renderer_has_no_ignored_mode_flag() -> None:
    assert "force_potentiostatic" not in inspect.signature(_render_impedance).parameters


def test_minimal_script_contains_only_chi_commands() -> None:
    script = ScriptGenerationService().generate(make_dod_request([20.0, 40.0])).minimal_script

    assert "TODO" not in script
    assert "#" not in script
    assert "=" in script
    assert all(not line.startswith(("说明", "公式", "warning")) for line in script.splitlines())
