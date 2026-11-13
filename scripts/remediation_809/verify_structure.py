"""Re-run the PR #809 structural compartmentalization proof."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else "22d23ddfc5cc2781c5ae210d0c1185c6176753fb"
LIMITS = (
    ("bilqis_mlx/runtime/_capability/factory/factory_retention_owner.py", 239),
    ("bilqis_mlx/runtime/_custody/bamf_bundle/publication.py", 239),
    ("bilqis_mlx/runtime/cognitive_solver.py", 239),
    ("bilqis_mlx/runtime/tests/capability/factory/owner/test_factory_retention_owner_live.py", 239),
)
DIRECTORIES = (
    ("bilqis_mlx/semantics/tests", 12),
    ("bilqis_mlx/runtime/tests/capability/factory", 12),
    ("bilqis_mlx/runtime/tests/capability/factory/retention", 12),
)


def main() -> int:
    subprocess.run(
        [sys.executable, "-B", "scripts/check_module_size.py", "--changed-from", BASE],
        cwd=ROOT, check=True,
    )
    for raw, limit in LIMITS:
        lines = len((ROOT / raw).read_text().splitlines())
        if lines > limit:
            raise SystemExit(f"STRUCTURE_FILE_LIMIT:{raw}:{lines}>{limit}")
    for raw, limit in DIRECTORIES:
        count = sum(p.suffix == ".py" and p.is_file() for p in (ROOT / raw).iterdir())
        if count > limit:
            raise SystemExit(f"STRUCTURE_DIRECTORY_LIMIT:{raw}:{count}>{limit}")
    print("REMEDIATION_809_STRUCTURE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
