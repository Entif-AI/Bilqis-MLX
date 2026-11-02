"""Readers for immutable historical semantic releases and capability aliases."""
from pathlib import Path as _Path

# Preserve historical module identities while grouping their physical owners.
__path__.extend(str(_Path(__file__).parent / group)
                for group in ("_history", "_recovery"))
del _Path
