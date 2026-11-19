"""Small orchestration helpers for the one-lineage #1300 closure witness."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator import operate_bamf


def one_visit(case, progress):
    return operate_bamf(
        case.run,
        minutes=1,
        max_visits=1,
        steps_per_visit=16,
        reserve_gib=0.0,
        source_prefetch_workers=0,
        parent_graph=case.parent_graph,
        progress=progress.append,
    )


def advance_until_admitted(case, progress, capability: str, *, limit: int = 8):
    """Let the production root converge until one capability enters the release."""
    results = []
    for _attempt in range(limit):
        results.append(one_visit(case, progress))
        release = read_accepted_atlas_factory_release(case.run)
        if capability in release.execution_plan.capability_map:
            return tuple(results), release, load_accepted_generation(case.run)
    case.fail(f"{capability} was not admitted within {limit} root visits")


def advance_until_stop(case, progress, *, limit: int = 8):
    """Continue through the production root until it emits an accountable stop."""
    accountable = {
        "PRIORITY_HOLD",
        "ADMISSION_HOLD",
        "IMPLEMENTATION_UNCOVERED",
        "FIXED_POINT",
    }
    for _attempt in range(limit):
        result = one_visit(case, progress)
        if result.status in accountable and result.stop_receipt_sha256 is not None:
            return result
    case.fail(f"production root did not emit an accountable stop within {limit} visits")


def cold_probe(run_dir: Path) -> dict:
    command = [
        sys.executable,
        "-m",
        "bilqis_mlx.runtime.tests.operator.conformance_1300_support.cold_probe",
        str(run_dir),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def cold_legal_next_probe(run_dir: Path) -> dict:
    command = [
        sys.executable,
        "-m",
        "bilqis_mlx.runtime.tests.operator.conformance_1300_support."
        "cold_legal_next_probe",
        str(run_dir),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)
