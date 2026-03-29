"""Compatibility entry point."""

from __future__ import annotations

from chi_generator.app import build_application


def main() -> int:
    app, window = build_application()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
