"""Learning proofs with stable shared-fixture imports across owner groups."""
from pathlib import Path

__path__.extend(str(Path(__file__).parent / name) for name in (
    "engram", "championship", "salience", "teaching", "custody",
))
