#!/usr/bin/env python3
"""Run pytest with the repository test package pinned before collection."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys


def _pin_repository_tests(root: Path) -> None:
    root = root.resolve()
    root_text = str(root)
    sys.path[:] = [root_text, *(entry for entry in sys.path if entry != root_text)]
    tests = importlib.import_module("tests")
    origin = Path(getattr(tests, "__file__", "")).resolve()
    expected = (root / "tests" / "__init__.py").resolve()
    if origin != expected:
        raise ImportError(
            f"unsafe pytest test package context: expected {expected}, got {origin}")


def main(argv: list[str] | None = None) -> int:
    root = Path.cwd().resolve()
    _pin_repository_tests(root)
    import pytest
    return pytest.main(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    raise SystemExit(main())
