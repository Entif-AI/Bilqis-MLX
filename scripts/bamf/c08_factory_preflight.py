"""Fail fast on C08 Factory witness plumbing before expensive MLX execution."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_ENV = ("BILQIS_A01_ATLAS_BUNDLE", "BILQIS_ATLAS_REAL_ARTIFACT")
FAST_TESTS = (
    "bilqis_mlx/runtime/tests/batch/test_factory_delivery_observation.py",
    "bilqis_mlx/runtime/tests/batch/test_factory_result_contract.py",
    "bilqis_mlx/runtime/tests/batch/test_atlas_candidate_step_custody.py",
)
REAL_PREFLIGHT = (
    "bilqis_mlx/runtime/tests/batch/factory/test_factory_training_preflight.py::"
    "FactoryTrainingPreflightTests::test_split_real_rows_reaches_gradient_boundary"
)


def _run(label: str, args: tuple[str, ...]) -> None:
    print(f"C08_PREFLIGHT_START {label}", flush=True)
    completed = subprocess.run(args, cwd=ROOT, check=False)
    print(
        f"C08_PREFLIGHT_END {label} returncode={completed.returncode}",
        flush=True,
    )
    if completed.returncode:
        raise SystemExit(completed.returncode)


def main() -> int:
    _run("FAST_CONTRACTS", (sys.executable, "-m", "pytest", "-q", *FAST_TESTS))
    missing = [name for name in ARTIFACT_ENV if not os.environ.get(name)]
    if missing:
        print("C08_PREFLIGHT_MISSING_ENV " + ",".join(missing), flush=True)
        return 2
    _run("REAL_FIXTURE", (sys.executable, "-m", "pytest", "-q", REAL_PREFLIGHT))
    print("C08_PREFLIGHT_OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
