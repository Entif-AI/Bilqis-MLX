"""Current/historical routine, promotion and generalization cohort lifetimes."""
from __future__ import annotations

import json
from collections import Counter

from ...curriculum.scheduler import assessment_capabilities
from ...generated_assessment import (GENERALIZATION_LIFECYCLE,
    PROMOTION_ATTEMPT_LIFECYCLE, ROUTINE_EVAL_LIFECYCLE, make_cohort,
    verify_stored_cohort)
from ...learning.stagnation_control import quarantined_capabilities
from ...live_curriculum import cohort_contract as _cohort_contract
from ..state import _seed, _state_from_json
from .common import _generalization_stratum
from .current_custody import (_draw_live_rows, _load_current_cohort,
    _persist_live_cohort)

def _grade_test_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Draw a fresh routine school-evaluation cohort at every exam boundary.

    Routine MAIN/RECOVERY evaluation is deliberately distinct from any
    promotion/graduation qualification attempt. Persisting a prior
    qualification_cohort must never freeze ordinary school evaluation.
    """
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(
        receipt,
        capability=f"ROUTINE_GRADE_EVAL:{school.grade}:{school.grade_exam_epoch}",
    )
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed, rubric_version=release)
    cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort, {"policy": ROUTINE_EVAL_LIFECYCLE,
                    "assessment_grade": school.grade,
                    "grade_exam_epoch": school.grade_exam_epoch,
                    "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                    "cohort_seed": cohort.seed}


def _promotion_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Materialize one distinct promotion-attempt cohort.

    The attempt is deterministic and crash-retry safe within the same durable
    generation, but a later promotion attempt receives a new seed and cohort.
    """
    school = _state_from_json(receipt["school"], course)
    existing = receipt.get("qualification_cohort")
    if (isinstance(existing, dict) and
            existing.get("policy") == PROMOTION_ATTEMPT_LIFECYCLE and
            existing.get("assessment_grade") == school.grade and
            existing.get("grade_exam_epoch") == school.grade_exam_epoch):
        return _load_current_cohort(run_dir, manifest, course, existing), dict(existing)
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(
        receipt,
        capability=f"PROMOTION_ATTEMPT:{school.grade}:{school.grade_exam_epoch}",
    )
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(
        rows, generator_version=generator, seed=seed, rubric_version=release)
    cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort, {"policy": PROMOTION_ATTEMPT_LIFECYCLE,
                    "assessment_grade": school.grade,
                    "grade_exam_epoch": school.grade_exam_epoch,
                    "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                    "cohort_seed": cohort.seed}


def _generalization_cohort(run_dir, receipt, manifest, course, source_root, graph,
                           *, promotion_sha256: str, exposed_specimen_ids=()):
    """Draw a never-reused fresh qualification cohort after promotion passes."""
    school = _state_from_json(receipt["school"], course)
    rubric, release, generator, _ = _cohort_contract(course)
    burned = receipt.get("burned_generalization_cohorts", ())
    if (not isinstance(burned, (tuple, list)) or
            any(not isinstance(item, str) or len(item) != 64 or
                any(char not in "0123456789abcdef" for char in item) for item in burned)):
        raise ValueError("HUMAN_TRAINER_GENERALIZATION_BURN_LEDGER_INVALID")
    excluded = set(exposed_specimen_ids)
    # A burn invalidates the prior *measurement instrument*, not every
    # correctly answered specimen forever. Training-exposed misses remain
    # excluded below, while an exact prior specimen set may never recur.
    burned_specimen_sets = set()
    for digest in (promotion_sha256, *burned):
        path = run_dir / "cohorts" / (digest + ".json")
        if path.is_symlink() or not path.is_file():
            raise ValueError("HUMAN_TRAINER_GENERALIZATION_EXPOSURE_EVIDENCE_MISSING")
        payload = json.loads(path.read_text())
        try:
            previous = verify_stored_cohort(payload, digest)
        except ValueError as exc:
            raise ValueError(
                "HUMAN_TRAINER_GENERALIZATION_EXPOSURE_CONTENT_DRIFT") from exc
        specimen_ids = frozenset(row["id"] for row in previous.rows)
        if digest == promotion_sha256:
            excluded.update(specimen_ids)
        else:
            burned_specimen_sets.add(specimen_ids)
    excluded.update(row["id"] for row in receipt.get("teacher_misses", ()))
    required = None
    selected = {}
    for attempt in range(128):
        seed = _seed(
            receipt,
            capability=f"GENERALIZATION:{school.grade}:{school.grade_exam_epoch}:{len(burned)}",
            step=attempt,
        )
        rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
        if required is None:
            required = Counter(_generalization_stratum(row) for row in rows)
        for row in rows:
            key = _generalization_stratum(row)
            if row["id"] not in excluded and len(selected.get(key, ())) < required[key]:
                selected.setdefault(key, []).append(row)
                excluded.add(row["id"])
        if any(len(selected.get(key, ())) != count for key, count in required.items()):
            continue
        cohort = make_cohort(
            [row for key in required for row in selected[key]],
            generator_version=generator, seed=seed, rubric_version=release)
        if (cohort.digest == promotion_sha256 or cohort.digest in burned or
                frozenset(row["id"] for row in cohort.rows) in burned_specimen_sets):
            continue
        cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
        return cohort, {"policy": GENERALIZATION_LIFECYCLE,
                        "assessment_grade": school.grade,
                        "grade_exam_epoch": school.grade_exam_epoch,
                        "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                        "cohort_seed": cohort.seed}
    raise ValueError("HUMAN_TRAINER_FRESH_GENERALIZATION_COHORT_EXHAUSTED")



def _candidate_cohort(run_dir, receipt, manifest, course, source_root, graph):
    """Fresh randomized qualification for checkpoint candidates, not graduation."""
    rubric, release, generator, _ = _cohort_contract(course)
    seed = _seed(receipt, capability="CANDIDATE_CHECKPOINT")
    rows = _draw_live_rows(source_root, graph, seed=seed, course=course)
    cohort = make_cohort(rows, generator_version=generator, seed=seed,
                         rubric_version=release)
    _persist_live_cohort(run_dir, manifest, course, cohort)
    return cohort


def _introduced_cohort(run_dir, manifest, course, school, cohort):
    """Activate only already introduced concepts from this generated cohort."""
    eligible = set(assessment_capabilities(course, school))
    rows = tuple(row for row in cohort.rows if row["capability"] in eligible)
    selected = cohort if rows == cohort.rows else make_cohort(rows,
        generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    return selected, _persist_live_cohort(run_dir, manifest, course, selected)


def _without_stagnant_capabilities(run_dir, manifest, course, cohort,
                                   control):
    """Remove current-session containment debt from ordinary evaluation only."""
    blocked = set(quarantined_capabilities(control))
    if not blocked:
        return cohort, _persist_live_cohort(run_dir, manifest, course, cohort)
    rows = tuple(row for row in cohort.rows if row["capability"] not in blocked)
    _require_active_stagnation_scope(rows)
    selected = make_cohort(
        rows, generator_version=cohort.generator_version, seed=cohort.seed,
        rubric_version=cohort.rubric_version)
    return selected, _persist_live_cohort(run_dir, manifest, course, selected)


def _require_active_stagnation_scope(scope) -> None:
    if not scope:
        raise ValueError("STAGNATION_ROUTINE_EVALUATION_HAS_NO_ACTIVE_CAPABILITIES")
