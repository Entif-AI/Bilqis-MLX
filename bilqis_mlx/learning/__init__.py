"""Teacher feedback, retention and championship owners.

Private source directories group physical files without creating replacement
module identities. Python resolves the existing ``learning.<owner>`` imports
through this package path. No owner is imported or executed eagerly.
"""
from pathlib import Path as _Path

_SOURCE_DIRECTORIES = (
    "_championship", "_salience", "_retention", "_engram", "_teaching",
)

__path__.extend(str(_Path(__file__).parent / name) for name in _SOURCE_DIRECTORIES)
