"""Package-local runtime proofs, preserving shared test fixture imports."""
from pathlib import Path

__path__.extend(str(Path(__file__).parent / name) for name in (
    "projection", "admission", "capability", "source", "model", "custody",
    "operator", "teacher", "depth", "correction", "batch",
))
