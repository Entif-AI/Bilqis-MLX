"""Serialized student execution, immutable artifacts and assessment custody.

Physical owner groups keep established runtime module imports stable while
reducing the directly resident runtime surface.
"""
from pathlib import Path

_OWNER_GROUPS = (
    "_projection",
    "_admission",
    "_batch",
    "_capability",
    "_correction",
    "_custody",
    "_depth",
    "_model",
    "_operator",
    "_source",
    "_teacher",
)

__path__.extend(str(Path(__file__).parent / name) for name in _OWNER_GROUPS)
