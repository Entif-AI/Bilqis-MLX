"""Serialized student execution, immutable artifacts and assessment custody.

Projection owners live in a dedicated directory while keeping their established
``bilqis_mlx.runtime`` module names and relative imports.
"""
from pathlib import Path

__path__.append(str(Path(__file__).parent / "_projection"))
