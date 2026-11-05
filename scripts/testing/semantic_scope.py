#!/usr/bin/env python3
"""Decide whether a change can affect Bilqis semantic verification surfaces."""
from __future__ import annotations

import argparse
from fnmatch import fnmatch
from pathlib import Path
import subprocess


SEMANTIC_PATTERNS = (
    "lib/ithkuil/**",
    "bilqis_mlx/semantics/**",
    "bilqis_mlx/source_adapters/**",
    "bilqis_mlx/factory/**",
    "bilqis_mlx/verification/**",
    "bilqis_mlx/diagnostics/**",
    "bilqis_mlx/_semantic_tools/**",
    "bilqis_mlx/_boolean_sources/**",
    "bilqis_mlx/_numeric_sources/**",
    "bilqis_mlx/_source_evidence/**",
    "bilqis_mlx/_release_views/**",
    "bilqis_mlx/_curriculum_compiler/**",
    "bilqis_mlx/_registry_ast/**",
    "bilqis_mlx/boolean*.py",
    "bilqis_mlx/curriculum.py",
    "bilqis_mlx/generated_assessment.py",
    "bilqis_mlx/grade_*.py",
    "bilqis_mlx/live_grade_*.py",
    "bilqis_mlx/numeric*.py",
    "bilqis_mlx/vocabulary_growth.py",
    "scripts/check_historical_abi.py",
    "scripts/check_semantic_boundaries.py",
    "scripts/tests/test_semantic_module_boundaries.py",
    "scripts/run_tests.py",
    ".github/workflows/semantic-profile-full.yml",
    ".github/workflows/semantic-abi-integrity.yml",
)


def is_semantic_path(path: str) -> bool:
    return any(fnmatch(path, pattern) for pattern in SEMANTIC_PATTERNS)


def semantic_changes(paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(path for path in paths if is_semantic_path(path))


def changed_paths(root: Path, base_ref: str) -> tuple[str, ...]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", base_ref, "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return tuple(line for line in proc.stdout.splitlines() if line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]

    if not args.base_ref or set(args.base_ref) == {"0"}:
        run = True
        reason = "BASE_REF_UNAVAILABLE"
        matches: tuple[str, ...] = ()
    else:
        matches = semantic_changes(changed_paths(root, args.base_ref))
        run = bool(matches)
        reason = "SEMANTIC_PATH_CHANGED" if run else "NO_SEMANTIC_PATH_CHANGES"

    print(f"SEMANTIC_SCOPE run={'true' if run else 'false'} reason={reason}")
    for path in matches:
        print(f"SEMANTIC_SCOPE_PATH {path}")
    if args.github_output:
        with args.github_output.open("a") as stream:
            stream.write(f"run={'true' if run else 'false'}\n")
            stream.write(f"reason={reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
