"""Matched read-only competence probe, distinct from the native C05 verdict."""
from __future__ import annotations

import hashlib
import json

from bilqis_mlx.runtime import factory_retention_owner as owner
from bilqis_mlx.runtime.capability_evaluation import _answer_identity

PROBE_SEED = 98317
PROBE_EACH = 6


def fixed_probe(context, parent, candidate, artifact, cache, training_rows):
    plan = context.release.execution_plan
    # Exact same seeded probe for both arms: target, untaught sibling, and
    # an earlier grade. This is a cross-capability check, not a claim that
    # the untrained genesis already has an earned protected baseline.
    caps = ("B.AND", "B.OR", next(item.capability_id for item in plan.capabilities
                                  if item.grade_id == "A"))
    rows = tuple(row for cap in caps for row in context.draw_rows(
        seed=PROBE_SEED, capability=cap, each=PROBE_EACH))
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids)) == len(caps) * PROBE_EACH
    assert not set(ids).intersection(row["id"] for row in training_rows)
    _, bundle, _, _ = owner._candidate_from_bound_parent(
        parent, cache, candidate, canonical_identity_required=False)
    instruments = owner._instruments(context, bundle, str(artifact), rows,
                                     seed=PROBE_SEED, each=PROBE_EACH,
                                     release_prevalidated=True)
    cases = tuple(item.case for item in instruments)
    assert len(cases) == len(rows)

    def scores(bundle, **kwargs):
        solver, generation = owner.factory_complete_solver(
            context, bundle, str(artifact), instruments, **kwargs)
        measured = solver.evaluate_cases(tuple(case.goal for case in cases), generation)
        return {cap: [sum(_answer_identity(result.answer) == _answer_identity(case.gold)
                          for case, (result, _) in zip(cases, measured)
                          if case.capability_id == cap), PROBE_EACH] for cap in caps}

    before = scores(parent, execution_cache=cache)
    after = scores(bundle)
    return {"seed": PROBE_SEED, "row_ids": ids,
            "cohort_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
            "training_row_overlap": 0, "parent_scores": before,
            "candidate_scores": after, "protected_baseline": "not established at genesis"}
