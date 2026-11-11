"""Fail fast on C08 Factory witness plumbing before expensive MLX execution."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET


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


def _run_pytest(label: str, tests: tuple[str, ...], minimum_tests: int) -> None:
    print(f"C08_PREFLIGHT_START {label}", flush=True)
    with TemporaryDirectory(prefix="c08-preflight-") as temp_dir:
        junit = Path(temp_dir) / "pytest.xml"
        completed = subprocess.run(
            (
                sys.executable,
                "-m",
                "pytest",
                "-q",
                f"--junitxml={junit}",
                *tests,
            ),
            cwd=ROOT,
            check=False,
        )
        if not junit.is_file():
            print(f"C08_PREFLIGHT_NO_JUNIT {label}", flush=True)
            raise SystemExit(completed.returncode or 2)
        root = ET.parse(junit).getroot()
        suites = (root,) if root.tag == "testsuite" else tuple(root.findall("testsuite"))
        counts = {
            name: sum(int(suite.attrib.get(name, "0")) for suite in suites)
            for name in ("tests", "failures", "errors", "skipped")
        }
    print(
        "C08_PREFLIGHT_END "
        f"{label} returncode={completed.returncode} "
        f"tests={counts['tests']} failures={counts['failures']} "
        f"errors={counts['errors']} skipped={counts['skipped']}",
        flush=True,
    )
    if (completed.returncode
            or counts["tests"] < minimum_tests
            or counts["failures"]
            or counts["errors"]
            or counts["skipped"]):
        raise SystemExit(completed.returncode or 2)


def main() -> int:
    _run_pytest("FAST_CONTRACTS", FAST_TESTS, minimum_tests=6)
    missing = [
        name for name in ARTIFACT_ENV
        if not os.environ.get(name) or not Path(os.environ[name]).is_dir()
    ]
    if missing:
        print("C08_PREFLIGHT_MISSING_ARTIFACT " + ",".join(missing), flush=True)
        return 2
    _run_pytest("REAL_FIXTURE", (REAL_PREFLIGHT,), minimum_tests=1)
    print("C08_PREFLIGHT_OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
