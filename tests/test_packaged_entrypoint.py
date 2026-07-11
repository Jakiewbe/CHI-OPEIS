import pytest

from chi_generator.main import main

pytestmark = pytest.mark.packaging


def test_smoke_entrypoint_imports_generator_and_exits(qt_app) -> None:
    assert main(["--smoke-test"]) == 0
