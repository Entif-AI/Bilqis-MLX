"""Route the bundled bounded fixture to the selected repository's canonical proof."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify-failures", action="store_true")
    args = parser.parse_args()
    fixture = Path(__file__).resolve().parents[1] / "assets/fixture"
    command = [str(args.python.absolute()), "-B", "-m", "lib.ithkuil.tests.ingestion_cleanroom",
               "--repo", str(args.repo.resolve()), "--fixture", str(fixture),
               "--output-root", str(args.output_root.resolve())]
    if args.verify_failures:
        command.append("--verify-failures")
    return subprocess.run(command, cwd=args.repo.resolve(), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
