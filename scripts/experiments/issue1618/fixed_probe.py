"""Matched read-only competence probe, distinct from the native C05 verdict."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json

from bilqis_mlx.runtime import factory_retention_owner as owner
from bilqis_mlx.runtime.capability_evaluation import _answer_identity

PROBE_SEED = 98317
PROBE_EACH = 6


@dataclass(frozen=True)
class PreparedProbe:
    seed: int
    capabilities: tuple[str, ...]
    row_ids: tuple[str, ...]
    instruments: tuple
    parent_scores: dict


def probe_rows(context, target, training_rows):
    """Resolve the sibling and earlier-grade probe from the admitted release."""
    plan = context.release.execution_plan
    target_grade = plan.capability_map[target].grade_id
    sibling = next(item.capability_id for item in plan.capabilities
                   if item.grade_id == target_grade and item.capability_id != target)
    earlier = next(item.capability_id for item in plan.capabilities
                   if item.grade_id == "A")
    caps = (target, sibling, earlier)
    assert len(set(caps)) == 3
    training_ids = {row["id"] for row in training_rows}
    for seed in range(PROBE_SEED, PROBE_SEED + 32):
        rows = tuple(row for cap in caps for row in context.draw_rows(
            seed=seed, capability=cap, each=PROBE_EACH))
        ids = {row["id"] for row in rows}
        if len(ids) == len(rows) == len(caps) * PROBE_EACH and not ids & training_ids:
            return seed, caps, rows
    raise ValueError("No row-disjoint fixed cohort in bounded seed window")


def _scores(context, bundle, artifact, instruments, caps, **kwargs):
    cases = tuple(item.case for item in instruments)
    assert Counter(case.capability_id for case in cases) == dict.fromkeys(caps, PROBE_EACH)
    solver, generation = owner.factory_complete_solver(
        context, bundle, str(artifact), instruments, **kwargs)
    measured = solver.evaluate_cases(tuple(case.goal for case in cases), generation)
    assert len(measured) == len(cases)
    return {cap: [sum(_answer_identity(result.answer) == _answer_identity(case.gold)
                      for case, (result, _) in zip(cases, measured, strict=True)
                      if case.capability_id == cap), PROBE_EACH] for cap in caps}


def prepare_probe(context, parent, artifact, cache, training_rows):
    """Draw, compile and exercise the exact probe before expensive training."""
    seed, caps, rows = probe_rows(context, "B.AND", training_rows)
    instruments = owner._instruments(context, parent, str(artifact), rows,
                                     seed=seed, each=PROBE_EACH,
                                     release_prevalidated=True)
    assert len(instruments) == len(rows)
    before = _scores(context, parent, artifact, instruments, caps, execution_cache=cache)
    return PreparedProbe(seed, caps, tuple(row["id"] for row in rows), instruments, before)


def fixed_probe(context, parent, candidate, artifact, cache, training_rows, prepared):
    assert not set(prepared.row_ids).intersection(row["id"] for row in training_rows)
    _, bundle, _, _ = owner._candidate_from_bound_parent(
        parent, cache, candidate, canonical_identity_required=False)
    after = _scores(context, bundle, artifact, prepared.instruments, prepared.capabilities)
    return {"seed": prepared.seed, "row_ids": prepared.row_ids,
            "cohort_sha256": hashlib.sha256(json.dumps(prepared.row_ids).encode()).hexdigest(),
            "training_row_overlap": 0, "parent_scores": prepared.parent_scores,
            "candidate_scores": after, "protected_baseline": "not established at genesis"}
