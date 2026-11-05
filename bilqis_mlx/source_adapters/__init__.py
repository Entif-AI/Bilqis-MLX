"""Read-only adapters from pinned historical source syntax to semantic ASTs."""

from pathlib import Path as _Path

# Preserve the long-standing source_adapters.<owner> import identities while
# physically compartmentalizing the crowded package root.
_PACKAGE_ROOT = _Path(__file__).resolve().parent
__path__.extend(str(_PACKAGE_ROOT / name) for name in ("_task_goals", "_events"))
del _PACKAGE_ROOT, _Path

from .catalog import bind_source_catalog
from .micro import from_micro_query

__all__ = ("bind_source_catalog", "from_micro_query")
