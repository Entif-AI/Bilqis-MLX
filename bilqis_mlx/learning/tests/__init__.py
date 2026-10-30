"""Learning-test package with compatibility search paths for relocated suites."""
from pathlib import Path

_ROOT = Path(__file__).parent
__path__.extend(str(_ROOT / name) for name in ("atlas", "championship", "teacher", "core", "frames"))
