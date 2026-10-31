"""Package-local runtime proofs while preserving historical test imports."""
from pathlib import Path

__path__.extend(str(Path(__file__).parent / name) for name in (
    "projection",
    "admission",
    "batch",
    "capability",
    "correction",
    "custody",
    "depth",
    "model",
    "operator",
    "source",
    "teacher",
))
