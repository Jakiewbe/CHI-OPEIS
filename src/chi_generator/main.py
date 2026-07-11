"""Compatibility entry point."""

from __future__ import annotations

import sys
import os
from collections.abc import Sequence

from chi_generator.app import build_application


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--smoke-test" in args:
        from chi_generator.domain.service import ScriptGenerationService

        ScriptGenerationService()
        if getattr(sys, "frozen", False):
            os._exit(0)
        return 0
    app, window = build_application()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
