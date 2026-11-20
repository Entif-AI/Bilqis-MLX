"""Small orchestration helpers for the one-lineage #1300 closure witness."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.factory_candidate_microbatch as candidate_microbatch
from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator import operate_bamf


def one_visit(case, progress):
    return operate_bamf(
        case.run,
        minutes=1,
        max_visits=1,
        steps_per_visit=1,
        reserve_gib=0.0,
        source_prefetch_workers=0,
        parent_graph=case.parent_graph,
        progress=progress.append,
    )


@contextmanager
def structural_certification_pass():
    """Qualify #1334/A09 structurally without making standalone efficacy a gate.

    The production certification owner still builds its real request, draws its
    real source-qualified cohort, persists the cohort, applies policy, commits
    scores, issues the accepted receipt, and drives the production successor
    path. A09 likewise retains its real obligation loop, source draws, source
    verification, evidence receipts, and action transitions. Only the disposable
    learner-answer predicates are fixed to source gold for this integration
    proof; learning quality is evaluated on the merged system, not by #1300.
    """
    def source_gold(
            _source_context, _parent, _atlas_artifact_path, rows,
            _source_draws, **_kwargs):
        return {row["id"]: row["gold"] for row in rows}

    scalar = candidate_microbatch.bamf_value_and_grad
    microbatch = candidate_microbatch.bamf_microbatch_value_and_grad

    def zero_gradients(result):
        """Keep boundary visits real but structurally non-learning."""
        for name, gradient in tuple(result.gradients.items()):
            result.gradients[name] = gradient * 0.0
        mx.eval(result.gradients)
        return result

    with patch(
            "bilqis_mlx.runtime.grade_certification_measurement."
            "GradeCertificationMeasurementBackend._row_correct",
            return_value=True), patch(
            "bilqis_mlx.runtime.bamf_operator.accepted_learning_evidence."
            "_accepted_predictions",
            side_effect=source_gold), patch.object(
            candidate_microbatch,
            "bamf_value_and_grad",
            side_effect=lambda *args, **kwargs: zero_gradients(
                scalar(*args, **kwargs))), patch.object(
            candidate_microbatch,
            "bamf_microbatch_value_and_grad",
            side_effect=lambda *args, **kwargs: zero_gradients(
                microbatch(*args, **kwargs))):
        yield


def advance_until_admitted(case, progress, capability: str, *, limit: int = 4):
    """Drive one real visit, then structurally close exact-checkpoint evidence.

    The first production-root visit is never skipped: a newborn capability must
    traverse the real teaching, optimizer, retention, publication, and baseline
    path before this witness may qualify the grade boundary.  Once that causal
    visit has happened, #1300 may fixture the *assessment result* rather than
    burn recovery rounds trying to prove standalone convergence.  The next
    production-root call still owns #1333 -> #1334 -> #1320 -> C07/B13 -> #1314.
    """
    results = []
    for _attempt in range(limit):
        result = one_visit(case, progress)
        results.append(result)
        release = read_accepted_atlas_factory_release(case.run)
        if capability in release.execution_plan.capability_map:
            return tuple(results), release, load_accepted_generation(case.run)

        # Evidence is checkpoint-bound.  After the real visit, qualify every
        # already admitted predecessor at the exact accepted checkpoint while
        # leaving the requested future capability outside the credited scope.
        # This is disposable witness evidence only; production policy remains
        # untouched and the boundary still executes through operate_bamf().
        from bilqis_mlx.runtime.atlas_flywheel_runtime import (
            AcceptedAtlasFlywheelSupervisor,
        )
        supervisor = AcceptedAtlasFlywheelSupervisor(
            case.run, case.parent_graph, reserve_gib=0.0)
        case._credit_all_predecessor_learning(
            supervisor, exclude=(capability,))

    case.fail(
        f"{capability} did not reach structurally qualified admission within "
        f"{limit} production-root visits"
    )


def assert_structural_admission_transition(case, before, after):
    """Require accepted structural progress without inventing a learning step."""
    case.assertGreater(after.generation, before.generation)
    case.assertGreaterEqual(
        after.retained_state.optimizer_step,
        before.retained_state.optimizer_step,
    )


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
