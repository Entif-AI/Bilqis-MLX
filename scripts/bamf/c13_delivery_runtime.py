"""Bounded production-owner execution for a disposable C13.1 run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf

from scripts.bamf.c13_delivery_contracts import CandidateAttemptReceipt

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


__all__ = ("attempt_owner_candidate", "cold_restart_identity", "run_candidate_attempts")
