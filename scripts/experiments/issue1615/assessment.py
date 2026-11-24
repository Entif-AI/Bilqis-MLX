"""A fixed row/content-disjoint competence sentinel plus actual C05 decision."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import time

import mlx.core as mx

from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.runtime import factory_retention_owner as owner
from bilqis_mlx.runtime.capability_evaluation import _answer_identity


PROBE_SEED = 98317
PROBE_EACH = 6


@dataclass(frozen=True)
class FixedProbe:
    seed: int
    capabilities: tuple
    row_ids: tuple
    input_keys: tuple
    instruments: tuple
    parent_scores: dict


def input_key(row):
    # Full source token sequence, independent of row ID or draw seed.
    return tuple(row["tokens"])


def probe_rows(context, target, training_rows):
    plan = context.release.execution_plan
    grade = plan.capability_map[target].grade_id
    sibling = next(item.capability_id for item in plan.capabilities
                   if item.grade_id == grade and item.capability_id != target)
    earlier = next(item.capability_id for item in plan.capabilities if item.grade_id == "A")
    caps = (target, sibling, earlier)
    if len(set(caps)) != 3:
        raise ValueError("This witness requires a Grade B target")
    training_ids = {row["id"] for row in training_rows}
    training_inputs = {input_key(row) for row in training_rows}
    for seed in range(PROBE_SEED, PROBE_SEED + 32):
        rows = tuple(row for cap in caps for row in context.draw_rows(
            seed=seed, capability=cap, each=PROBE_EACH))
        ids = {row["id"] for row in rows}
        inputs = {input_key(row) for row in rows}
        if (len(ids) == len(rows) == len(caps) * PROBE_EACH
                and not ids & training_ids and not inputs & training_inputs):
            return seed, caps, rows
    raise ValueError("No disjoint fixed cohort in bounded seed window")


def scores(context, bundle, artifact, instruments, caps, **kwargs):
    cases = tuple(item.case for item in instruments)
    if Counter(case.capability_id for case in cases) != dict.fromkeys(caps, PROBE_EACH):
        raise AssertionError("Fixed cohort coverage drift")
    solver, generation = owner.factory_complete_solver(
        context, bundle, str(artifact), instruments, **kwargs)
    measured = solver.evaluate_cases(tuple(case.goal for case in cases), generation)
    return {cap: [sum(_answer_identity(result.answer) == _answer_identity(case.gold)
                      for case, (result, _) in zip(cases, measured, strict=True)
                      if case.capability_id == cap), PROBE_EACH] for cap in caps}


def prepare(context, parent, artifact, cache, target, training_rows):
    seed, caps, rows = probe_rows(context, target, training_rows)
    instruments = owner._instruments(context, parent, str(artifact), rows,
                                     seed=seed, each=PROBE_EACH, release_prevalidated=True)
    before = scores(context, parent, artifact, instruments, caps, execution_cache=cache)
    return FixedProbe(seed, caps, tuple(row["id"] for row in rows),
                      tuple(input_key(row) for row in rows), instruments, before)


def finish(context, parent, transaction, artifact, cache, training_rows, prepared,
           run_dir, target, training_wall):
    if (set(prepared.row_ids).intersection(row["id"] for row in training_rows)
            or set(prepared.input_keys).intersection(input_key(row) for row in training_rows)):
        raise AssertionError("Assessment overlaps training")
    started = time.perf_counter()
    evaluation = owner.evaluate_factory_retention_candidate(
        context, transaction, str(artifact), target, run_dir=run_dir,
        accepted_parent=parent, execution_cache=cache)
    issued = issue_factory_retention_decision(evaluation)
    mx.synchronize()
    retention_seconds = time.perf_counter() - started
    attempt_seconds = training_wall + retention_seconds
    peak = int(mx.get_peak_memory())
    _, bundle, _, _ = owner._candidate_from_bound_parent(
        parent, cache, transaction, canonical_identity_required=False)
    after = scores(context, bundle, artifact, prepared.instruments, prepared.capabilities)
    before = prepared.parent_scores
    accepted = bool(issued.accepted)
    retained = after if accepted else before
    return {
        "retention_accepted": accepted, "retention_reason": evaluation.decision.reason,
        "retention_outcome_scores": evaluation.decision.outcome_scores,
        "retention_evidence_sha256": evaluation.decision.evidence_sha256,
        "retention_seconds": retention_seconds, "attempt_seconds": attempt_seconds,
        "completed_candidate_trials_per_hour": 3600 / attempt_seconds,
        "attempted_steps_per_minute": transaction.update_steps * 60 / attempt_seconds,
        "training_and_c05_peak_mlx_bytes": peak,
        "fixed_probe": {"seed": prepared.seed, "capabilities": prepared.capabilities,
            "row_ids": prepared.row_ids,
            "cohort_sha256": hashlib.sha256(json.dumps(prepared.row_ids).encode()).hexdigest(),
            "training_row_overlap": 0, "training_token_sequence_overlap": 0,
            "independence_scope": "held-out generated episodes, not source-family transfer",
            "parent_scores": before, "candidate_scores": after,
            "retention_selected_scores": retained,
            "candidate_correct_change_per_hour": {
                cap: (after[cap][0] - before[cap][0]) * 3600 / attempt_seconds for cap in before},
            "retention_selected_correct_change_per_hour": {
                cap: (retained[cap][0] - before[cap][0]) * 3600 / attempt_seconds for cap in before}}}
