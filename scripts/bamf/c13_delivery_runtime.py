"""Bounded production-owner execution for a disposable C13.1 run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf

from scripts.bamf.c13_delivery_contracts import CandidateAttemptReceipt, SemanticDeltaReceipt

PRODUCTION_RESERVE_GIB = 100.0
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _identity(student) -> str:
    return candidate_identity_digest(student.retained_state)


def cold_restart_identity(run_dir: Path) -> dict:
    """Reload accepted B13 state in a fresh Python process and compare identity."""
    run_dir = Path(run_dir).resolve()
    parent = load_accepted_generation(run_dir)
    expected = {
        "generation": parent.generation,
        "optimizer_step": parent.retained_state.optimizer_step,
        "candidate_identity_sha256": _identity(parent),
    }
    script = "\n".join((
        "import json,sys",
        "from pathlib import Path",
        "from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest",
        "from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation",
        "student=load_accepted_generation(Path(sys.argv[1]))",
        "print(json.dumps({'generation':student.generation,'optimizer_step':student.retained_state.optimizer_step,'candidate_identity_sha256':candidate_identity_digest(student.retained_state)},sort_keys=True))",
    ))
    completed = subprocess.run(
        [sys.executable, "-c", script, str(run_dir)],
        cwd=str(_REPOSITORY_ROOT),
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("BAMF_C13_COLD_RESTART_FAILED:" + completed.stderr[-1000:])
    try:
        observed = json.loads(completed.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise RuntimeError("BAMF_C13_COLD_RESTART_OUTPUT_INVALID") from error
    if observed != expected:
        raise RuntimeError("BAMF_C13_COLD_RESTART_IDENTITY_DRIFT")
    return observed


def attempt_owner_candidate(run_dir: Path) -> CandidateAttemptReceipt:
    parent = load_accepted_generation(run_dir)
    result = operate_bamf(
        run_dir, minutes=1, max_visits=1, reserve_gib=PRODUCTION_RESERVE_GIB)
    current = load_accepted_generation(run_dir)
    if result.accepted == 1 and result.rejected == 0 and result.visits == 1:
        outcome = "ACCEPTED"
    elif result.rejected == 1 and result.accepted == 0 and result.visits == 1:
        outcome = "REJECTED"
    elif result.status == "PRIORITY_HOLD" and result.visits == 0:
        outcome = "HELD"
    elif result.status == "ACTION_REQUIRED" and result.visits == 0:
        outcome = "ACTION_REQUIRED"
    else:
        raise ValueError("BAMF_C13_OWNER_VISIT_RESULT_INVALID")
    return CandidateAttemptReceipt(
        outcome,
        parent.generation,
        current.generation,
        parent.retained_state.optimizer_step,
        current.retained_state.optimizer_step,
        _identity(parent),
        _identity(current),
        int(outcome in ("ACCEPTED", "REJECTED")),
    )


def run_candidate_attempts(
    run_dir: Path, max_steps: int,
) -> tuple[CandidateAttemptReceipt, ...]:
    attempts = []
    spent = 0
    while spent < max_steps:
        receipt = attempt_owner_candidate(run_dir)
        attempts.append(receipt)
        spent += receipt.attempted_steps
        if receipt.outcome in ("REJECTED", "HELD", "ACTION_REQUIRED"):
            break
        if {item.outcome for item in attempts} >= {"ACCEPTED", "REJECTED"}:
            break
    return tuple(attempts)


def _assert_optimizer_prefix(parent, current, *, mutable_rows_by_key=None) -> None:
    for field in ("parameters", "m", "v", "update_counts"):
        before_tree = getattr(parent.retained_state.optimizer, field)
        after_tree = getattr(current.retained_state.optimizer, field)
        if set(after_tree) != set(before_tree):
            raise ValueError("BAMF_C13_SEMANTIC_DELTA_OPTIMIZER_KEYS_DRIFT")
        for key, before_value in before_tree.items():
            before = np.asarray(before_value)
            after = np.asarray(after_tree[key])
            if after.dtype != before.dtype or after.ndim != before.ndim:
                raise ValueError("BAMF_C13_SEMANTIC_DELTA_OPTIMIZER_SHAPE_DRIFT")
            if any(new < old for old, new in zip(before.shape, after.shape)):
                raise ValueError("BAMF_C13_SEMANTIC_DELTA_OPTIMIZER_SHRANK")
            prefix = tuple(slice(0, size) for size in before.shape)
            mutable_rows = () if mutable_rows_by_key is None else mutable_rows_by_key.get(key, ())
            if field == "parameters" and mutable_rows:
                stable = np.asarray(
                    [row for row in range(before.shape[0]) if row not in mutable_rows],
                    dtype=np.intp)
                if stable.size:
                    np.testing.assert_array_equal(
                        after[(stable, *prefix[1:])], before[stable])
            else:
                np.testing.assert_array_equal(after[prefix], before)


def record_append_only_semantic_delta(
    parent, current, semantic_id: str,
) -> SemanticDeltaReceipt:
    """Validate the C13 boundary around an already-authorized C07 parameter extension."""
    if current.generation != parent.generation + 1:
        raise ValueError("BAMF_C13_SEMANTIC_DELTA_GENERATION_DRIFT")
    parent_step = parent.retained_state.optimizer_step
    if current.retained_state.optimizer_step != parent_step:
        raise ValueError("BAMF_C13_SEMANTIC_DELTA_OPTIMIZER_STEP_DRIFT")
    parent_ages = {item.identity: item for item in parent.retained_state.policy.row_ages}
    current_ages = {item.identity: item for item in current.retained_state.policy.row_ages}
    if not set(parent_ages).issubset(current_ages):
        raise ValueError("BAMF_C13_SEMANTIC_DELTA_ROW_REMOVAL")
    for identity, before in parent_ages.items():
        if current_ages[identity] != before:
            raise ValueError("BAMF_C13_SEMANTIC_DELTA_OLD_ROW_DRIFT")
    new = tuple(item for identity, item in current_ages.items() if identity not in parent_ages)
    if len(new) != 1 or new[0].accepted_age != 0:
        raise ValueError("BAMF_C13_SEMANTIC_DELTA_NEW_ROW_INVALID")
    mutable_rows = {f"identity.bank.{new[0].bank_index}": (new[0].row_index,)}
    _assert_optimizer_prefix(parent, current, mutable_rows_by_key=mutable_rows)
    return SemanticDeltaReceipt(
        semantic_id,
        parent.generation,
        current.generation,
        parent_step,
        True,
        ((new[0].bank_index, new[0].row_index),),
    )


__all__ = (
    "attempt_owner_candidate", "cold_restart_identity", "record_append_only_semantic_delta",
    "run_candidate_attempts",
)
