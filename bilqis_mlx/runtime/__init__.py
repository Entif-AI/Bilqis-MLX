"""Serialized student execution, immutable artifacts and assessment custody.

Grouped runtime owners keep their established ``bilqis_mlx.runtime`` module
names and relative imports.
"""
from pathlib import Path

_OWNER_GROUPS = (
    "_projection", "_admission", "_capability", "_source", "_model", "_custody",
    "_operator", "_teacher", "_depth", "_correction", "_batch",
)
__path__.extend(str(Path(__file__).parent / name) for name in _OWNER_GROUPS)
