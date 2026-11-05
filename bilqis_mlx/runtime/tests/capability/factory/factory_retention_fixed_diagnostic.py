"""Non-authorizing fixed-school capability diagnostic for C05 protected losses."""
from __future__ import annotations

from pathlib import Path
from time import perf_counter

from bilqis_mlx.fixed_frontier import frontier_exam, load_frontier_cohort
from bilqis_mlx.learning.retention_policy import scaled_loss_allowance
from bilqis_mlx.runtime.capability_evaluation import _answer_identity
from bilqis_mlx.runtime.factory_complete_solver import factory_complete_solver
from bilqis_mlx.runtime.factory_retention_owner import (
    C05_PROBE_EACH, C05_PROTECTED_REFERENCE_LOSS,
    _candidate_from_live_parent, _instruments, _training_exclusions,
)
from bilqis_mlx.state_dag import read_current

from .factory_retention_target_diagnostic import _value_receipt


def diagnose_fixed_capability(
    source_context,
    candidate,
    artifact_path: str,
    target_capability: str,
    protected_capability: str,
    *,
    run_dir: Path,
):
    """Measure one fixed protected capability without issuing retention authority."""
    started = perf_counter()
    source_context.__post_init__()
    release = source_context.release
    capability_map = release.execution_plan.capability_map
    if target_capability not in capability_map or protected_capability not in capability_map:
        raise AssertionError("C05 fixed diagnostic capability is not admitted")
    training = _training_exclusions(candidate)
    if any(
        authority.delivery_capability != target_capability
        or authority.release_sha256 != release.release_sha256
        for authority in candidate.training_authorities
    ):
        raise AssertionError("C05 fixed diagnostic training authority drift")

    parent, candidate_bundle, _candidate_state, _cache = _candidate_from_live_parent(
        run_dir, candidate)
    receipt = read_current(run_dir)
    if receipt.get("factory_release_sha256") != release.release_sha256:
        raise AssertionError("C05 fixed diagnostic Factory release drift")
    exam = frontier_exam(receipt)
    fixed = load_frontier_cohort(run_dir, exam)
    if fixed is None or exam.get("factory_release_sha256") != release.release_sha256:
        raise AssertionError("C05 fixed diagnostic cohort unavailable")
    rows = tuple(
        row for row in fixed.rows
        if row.get("capability") == protected_capability)
    if not rows:
        raise AssertionError("C05 fixed diagnostic protected capability absent")
    bound = perf_counter()

    instruments = _instruments(
        source_context, candidate_bundle, artifact_path, rows, seed=fixed.seed)
    instruments_done = perf_counter()
    parent_solver, parent_generation = factory_complete_solver(
        source_context, parent, artifact_path, instruments)
    candidate_solver, candidate_generation = factory_complete_solver(
        source_context, candidate_bundle, artifact_path, instruments)
    solvers_done = perf_counter()

    parent_correct = candidate_correct = 0
    cases = []
    for instrument in instruments:
        case = instrument.case
        parent_at = perf_counter()
        parent_result, parent_contract = parent_solver.evaluate(
            case.goal, parent_generation)
        parent_done = perf_counter()
        candidate_result, candidate_contract = candidate_solver.evaluate(
            case.goal, candidate_generation)
        candidate_done = perf_counter()
        parent_match = _answer_identity(parent_result.answer) == _answer_identity(case.gold)
        candidate_match = (
            _answer_identity(candidate_result.answer) == _answer_identity(case.gold))
        parent_correct += int(parent_match)
        candidate_correct += int(candidate_match)
        cases.append({
            "case_id": case.case_id,
            "gold": _value_receipt(case.gold),
            "parent": {
                "correct": parent_match,
                "answer": _value_receipt(parent_result.answer),
                "route": parent_result.route.value,
                "neural_calls": parent_result.neural_calls,
                "fallback_reason": parent_result.fallback_reason,
                "solve_seconds": parent_done - parent_at,
            },
            "candidate": {
                "correct": candidate_match,
                "answer": _value_receipt(candidate_result.answer),
                "route": candidate_result.route.value,
                "neural_calls": candidate_result.neural_calls,
                "fallback_reason": candidate_result.fallback_reason,
                "solve_seconds": candidate_done - parent_done,
            },
            "solver_contract_match": parent_contract == candidate_contract,
        })

    total = len(instruments)
    delta = candidate_correct - parent_correct
    allowance = scaled_loss_allowance(
        total, C05_PROTECTED_REFERENCE_LOSS, C05_PROBE_EACH)
    finished = perf_counter()
    return {
        "schema": "bilqis.mlx.c05-fixed-capability-diagnostic/v1",
        "authorizing": False,
        "target_capability": target_capability,
        "protected_capability": protected_capability,
        "fixed_seed": fixed.seed,
        "training_family_ids": training[0],
        "training_episode_ids": training[1],
        "parent_generation": parent_generation,
        "candidate_generation": candidate_generation,
        "parent_correct": parent_correct,
        "candidate_correct": candidate_correct,
        "total": total,
        "delta": delta,
        "protected_loss_allowance": allowance,
        "blocked": -delta > allowance,
        "cases": cases,
        "timing_seconds": {
            "bind_and_select": bound - started,
            "instrument_compile": instruments_done - bound,
            "solver_build": solvers_done - instruments_done,
            "solve": finished - solvers_done,
            "total": finished - started,
        },
    }


__all__ = ("diagnose_fixed_capability",)
