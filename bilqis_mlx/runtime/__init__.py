"""Serialized student execution, immutable artifacts and assessment custody.

Grouped runtime owners keep their established ``bilqis_mlx.runtime`` module
names and relative imports.
"""
from pathlib import Path

__path__.extend(str(Path(__file__).parent / name) for name in ("_projection", "_admission"))
