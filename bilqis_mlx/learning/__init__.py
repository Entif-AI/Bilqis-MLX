"""Teacher feedback, retention and championship owners with stable imports."""
from pathlib import Path

_ROOT = Path(__file__).parent
__path__.extend(str(_ROOT / name) for name in ("atlas", "championship", "teacher", "core"))
