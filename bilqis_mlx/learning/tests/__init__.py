"""Tests for learning owners, preserving their established helper imports."""
from pathlib import Path as _Path

from .. import _SOURCE_DIRECTORIES

__path__.extend(
    str(_Path(__file__).parents[1] / name / "tests") for name in _SOURCE_DIRECTORIES
)
