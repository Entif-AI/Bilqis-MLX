"""Run local CI tests with the Studio's single-process MLX memory bound."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    if not args or (args[0] == "-m" and len(args) < 2):
        raise SystemExit("Expected a Python script or -m module")
    try:
        import mlx.core as mx
    except ModuleNotFoundError:
        mx = None
    if mx is not None:
        mx.set_memory_limit(12 * 1024**3)
        mx.set_cache_limit(0)
    try:
        if args[0] == "-m":
            sys.argv = args[1:]
            runpy.run_module(args[1], run_name="__main__", alter_sys=True)
        else:
            sys.argv = args
            sys.path.insert(0, str(Path(args[0]).resolve().parent))
            runpy.run_path(args[0], run_name="__main__")
    finally:
        if mx is not None:
            mx.clear_cache()


if __name__ == "__main__":
    main()
