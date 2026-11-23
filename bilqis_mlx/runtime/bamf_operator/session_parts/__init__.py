"""Private session-composition helpers for the BAMF operator."""
from pathlib import Path


_OWNER_GROUPS = ("_candidate", "_lifecycle")
__path__.extend(str(Path(__file__).parent / name) for name in _OWNER_GROUPS)
