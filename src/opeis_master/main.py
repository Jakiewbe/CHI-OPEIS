"""Compatibility entry point."""

from __future__ import annotations

from chi_generator.main import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
