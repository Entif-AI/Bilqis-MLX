#!/usr/bin/env python3
"""Orchestrate disposable #1578 accelerator-work-unit qualification."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bilqis_mlx.runtime.accelerator_work_units import (
    C08_EQUIVALENCE_ATOL,
    DEFAULT_LOGICAL_BATCH_SIZE,
    PHYSICAL_CAPS,
    classify_physical_row_work_unit,
    equal_row_budget_schedule,
    physical_result_contract_equivalent,
)

PHYSICAL_ARM = Path(__file__).with_name("issue1578_physical_arm.py")
LOGICAL_ARM = Path(__file__).with_name("issue1578_logical_arm.py")


def _run_arm(
    root: Path,
    script: Path,
    marker: str,
    environment: dict[str, str],
) -> dict:
    process = subprocess.Popen(
        [sys.executable, "-B", str(script)],
        cwd=root,
        env={**os.environ, "BILQIS_TEST_WORKERS": "1", **environment},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    matches = []
    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)
        if line.startswith(marker + " "):
            matches.append(line.rstrip())
    returncode = process.wait()
    if returncode != 0:
        raise SystemExit(f"#1578 arm failed with return code {returncode}")
    if len(matches) != 1:
        raise SystemExit(f"#1578 expected exactly one {marker} record")
    return json.loads(matches[0].split(" ", 1)[1])


def _physical(root: Path, artifact_rel: str) -> dict:
    results = tuple(
        _run_arm(
            root,
            PHYSICAL_ARM,
            "ISSUE1578_PHYSICAL_RESULT",
            {
                "ISSUE1578_ARTIFACT_REL": artifact_rel,
                "ISSUE1578_LOGICAL_ROWS": str(DEFAULT_LOGICAL_BATCH_SIZE),
                "ISSUE1578_PHYSICAL_CAP": str(cap),
            },
        )
        for cap in PHYSICAL_CAPS
    )
    equivalent = physical_result_contract_equivalent(results)
    bitwise_state_equal = (
        len({result["optimizer_state_sha256"] for result in results}) == 1
    )
    larger = classify_physical_row_work_unit(
        logical_batch_size=DEFAULT_LOGICAL_BATCH_SIZE,
        rows_per_launch=64,
    )
    return {
        "schema": "bilqis.bamf.issue1578-physical-geometry/v1",
        "logical_batch_size": DEFAULT_LOGICAL_BATCH_SIZE,
        "results": results,
        "equivalent_optimizer_objective": equivalent,
        "c08_equivalence_atol": C08_EQUIVALENCE_ATOL,
        "optimizer_state_bitwise_equal": bitwise_state_equal,
        "optimizer_state_bitwise_note": (
            "Diagnostic only. C08 microbatch equivalence is an FP32 numerical "
            "contract; reduction-order differences need not be bit-identical."
        ),
        "larger_row_launch": {
            "rows_per_launch": 64,
            "status": larger.status,
            "learning_policy_change": larger.learning_policy_change,
            "reason": (
                "A row-count work unit cannot contain more rows than the exact "
                "logical optimizer objective without crossing logical-step "
                "membership; sequential steps consume updated AdamW state."
            ),
        },
    }


def _logical(root: Path, artifact_rel: str, row_budget: int) -> dict:
    results = tuple(
        _run_arm(
            root,
            LOGICAL_ARM,
            "ISSUE1578_LOGICAL_RESULT",
            {
                "ISSUE1578_ARTIFACT_REL": artifact_rel,
                "ISSUE1578_LOGICAL_BATCH_SIZE": str(arm.logical_batch_size),
                "ISSUE1578_HORIZON": str(arm.optimizer_steps),
            },
        )
        for arm in equal_row_budget_schedule(row_budget=row_budget)
    )
    return {
        "schema": "bilqis.bamf.issue1578-logical-batch-experiment/v1",
        "row_budget": row_budget,
        "learning_policy_experiment": True,
        "results": results,
        "default_batch_size_changed": False,
        "useful_retentions_per_hour": "NOT_MEASURED",
    }


def _contract(row_budget: int) -> dict:
    return {
        "schema": "bilqis.bamf.issue1578-accelerator-work-units/v1",
        "default_logical_batch_size": DEFAULT_LOGICAL_BATCH_SIZE,
        "physical_caps": list(PHYSICAL_CAPS),
        "equal_row_budget_schedule": [
            {
                "logical_batch_size": arm.logical_batch_size,
                "optimizer_steps": arm.optimizer_steps,
                "row_presentations": arm.row_presentations,
                "learning_policy_experiment": arm.learning_policy_experiment,
            }
            for arm in equal_row_budget_schedule(row_budget=row_budget)
        ],
        "default_batch_size_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--mode",
        choices=("contract", "physical", "logical", "all"),
        default="contract",
    )
    parser.add_argument("--row-budget", type=int, default=96)
    parser.add_argument(
        "--artifact-rel",
        default=(
            "bilqis_mlx/bootstrap_assets/atlas/"
            "5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7"
        ),
    )
    args = parser.parse_args()
    root = args.root.resolve()
    contract = _contract(args.row_budget)
    if args.mode in ("physical", "all"):
        contract["physical"] = _physical(root, args.artifact_rel)
    if args.mode in ("logical", "all"):
        contract["logical"] = _logical(root, args.artifact_rel, args.row_budget)
    print("ISSUE1578_QUALIFICATION " + json.dumps(contract, sort_keys=True))
    if (
        "physical" in contract
        and not contract["physical"]["equivalent_optimizer_objective"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
