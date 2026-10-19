"""Source cohort persistence and routine, promotion and generalization lifetimes."""
from __future__ import annotations

import json
from collections import Counter

from ..generated_assessment import (
    GENERALIZATION_LIFECYCLE, PROMOTION_ATTEMPT_LIFECYCLE,
    ROUTINE_EVAL_LIFECYCLE, make_cohort,
)
from ..live_curriculum import cohort_contract as _cohort_contract, draw_course_rows, lesson_contract
from bilqis_mlx.curriculum.scheduler import assessment_capabilities
from bilqis_mlx.learning.stagnation_control import quarantined_capabilities
from .state import _durable_json, _seed, _state_from_json

def _draw_live_rows(source_root, graph, *, seed, capability=None, each=None, course=None):
    """Draw only through the verified course/factory source boundary."""
    if course is None:
        raise ValueError("FACTORY_RELEASE_REQUIRED_FOR_SOURCE_GENERATION")
    return draw_course_rows(source_root, graph, course, seed=seed,
                            capability=capability, each=each)


def _persist_live_cohort(run_dir, manifest, course, cohort):
    """Make generation retry safe if a crash follows cohort publication."""
    rubric, release, generator, code_sha = _cohort_contract(course)
    if cohort.generator_version != generator or cohort.rubric_version != release:
        raise ValueError("HUMAN_TRAINER_COHORT_VERSION_MISMATCH")
    path = run_dir / "cohorts" / (cohort.digest + ".json")
    payload = {"schema": release,
               "source_manifest_sha256": manifest["manifest_sha256"],
               "rubric_sha256": rubric,
               "generator_version": generator,
               "generator_code_sha256": code_sha,
               "seed": cohort.seed,
               "cohort_sha256": cohort.digest, "rows": list(cohort.rows)}
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text()) != payload:
            raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_CUSTODY_DRIFT")
    else:
        _durable_json(path, payload)
    if json.loads(path.read_text()) != payload:
        raise ValueError("HUMAN_TRAINER_GENERATED_COHORT_WRITEBACK_DRIFT")
    return str(path.relative_to(run_dir))


def _load_current_cohort(run_dir, manifest, course, pointer):
    """Read back one current-release cohort without changing its qualification state."""
    if not isinstance(pointer, dict):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_INVALID")
    sha = pointer.get("cohort_sha256")
    path_ref = pointer.get("cohort_file")
    if (not isinstance(sha, str) or len(sha) != 64 or
            path_ref != "cohorts/" + sha + ".json"):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_DRIFT")
    path = run_dir / path_ref
    if path.is_symlink() or not path.is_file():
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_MISSING")
    stored = json.loads(path.read_text())
    rubric, release, generator, code_sha = _cohort_contract(course)
    if (stored.get("schema") != release or
            stored.get("source_manifest_sha256") != manifest["manifest_sha256"] or
            stored.get("rubric_sha256") != rubric or
            stored.get("generator_version") != generator or
            stored.get("generator_code_sha256") != code_sha or
            stored.get("cohort_sha256") != sha or
            stored.get("seed") != pointer.get("cohort_seed")):
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_METADATA_DRIFT")
    cohort = make_cohort(stored["rows"], generator_version=generator,
                         seed=stored["seed"], rubric_version=release)
    if cohort.digest != sha:
        raise ValueError("HUMAN_TRAINER_COHORT_POINTER_CONTENT_DRIFT")
    return cohort


def load_championship_cohort(run_dir, witness):
    """Verify an immutable earning cohort against its own admitted source identity."""
    sha = witness.get("cohort_sha256")
    if (not isinstance(sha, str) or len(sha) != 64 or
            any(char not in "0123456789abcdef" for char in sha)):
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_IDENTITY_REQUIRED")
    path = run_dir / "cohorts" / (sha + ".json")
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_MISSING")
    stored = json.loads(path.read_text())
    if (stored.get("cohort_sha256") != sha or
            stored.get("rubric_sha256") != witness["rubric_sha256"] or
            stored.get("source_manifest_sha256") != witness["source_oracle_sha256"]):
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_SOURCE_DRIFT")
    cohort = make_cohort(stored["rows"], generator_version=stored["generator_version"],
                         seed=stored["seed"], rubric_version=stored["schema"])
    if cohort.digest != sha:
        raise ValueError("CHAMPIONSHIP_EARNING_COHORT_CONTENT_DRIFT")
    return cohort


def _verify_saved_cohort(run_dir, receipt, course):
    exam = receipt.get("last_exam") or {}
    sha = exam.get("cohort_sha256")
    if sha is None:
        return  # Migration may still point at an archived fixed-rubric exam.
    if (not isinstance(sha, str) or len(sha) != 64 or
            exam.get("cohort_file") != "cohorts/" + sha + ".json"):
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_REFERENCE_DRIFT")
    path = run_dir / exam["cohort_file"]
    if path.is_symlink() or not path.is_file():
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_MISSING")
    stored = json.loads(path.read_text())
    # Archived cohorts remain verifiable after later grade admissions; resolve
    # their source contract by the release embedded in the cohort, not grade ID.
    contracts = [lesson_contract(course, grade.id) for grade in course.grades]
    matches = [contract for contract in contracts if contract[1] == stored.get("schema")]
    if len(matches) == 1:
        rubric, release, generator, code_sha = matches[0]
    elif stored.get("schema") == course.version:
        rubric, release, generator, code_sha = _cohort_contract(course)
    else:
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_RELEASE_NOT_ADMITTED")
    if (stored.get("rubric_sha256") != rubric or
            stored.get("source_manifest_sha256") != receipt["source_manifest_sha256"] or
            stored.get("generator_version") != generator or
            stored.get("generator_code_sha256") != code_sha or
            stored.get("cohort_sha256") != sha or
            stored.get("seed") != exam.get("cohort_seed") or
            stored.get("schema") != release):
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_METADATA_DRIFT")
    cohort = make_cohort(stored["rows"], generator_version=generator,
                         seed=stored["seed"], rubric_version=release)
    if cohort.digest != sha:
        raise ValueError("HUMAN_TRAINER_SAVED_COHORT_CONTENT_DRIFT")
    return cohort


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
    for digest in (promotion_sha256, *burned):
        path = run_dir / "cohorts" / (digest + ".json")
        if path.is_symlink() or not path.is_file():
            raise ValueError("HUMAN_TRAINER_GENERALIZATION_EXPOSURE_EVIDENCE_MISSING")
        payload = json.loads(path.read_text())
        previous = make_cohort(payload["rows"], seed=payload["seed"],
                               generator_version=payload["generator_version"],
                               rubric_version=payload["schema"])
        if previous.digest != digest or payload.get("cohort_sha256") != digest:
            raise ValueError("HUMAN_TRAINER_GENERALIZATION_EXPOSURE_CONTENT_DRIFT")
        excluded.update(row["id"] for row in previous.rows)
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
        if cohort.digest == promotion_sha256 or cohort.digest in burned:
            continue
        cohort_file = _persist_live_cohort(run_dir, manifest, course, cohort)
        return cohort, {"policy": GENERALIZATION_LIFECYCLE,
                        "assessment_grade": school.grade,
                        "grade_exam_epoch": school.grade_exam_epoch,
                        "cohort_sha256": cohort.digest, "cohort_file": cohort_file,
                        "cohort_seed": cohort.seed}
    raise ValueError("HUMAN_TRAINER_FRESH_GENERALIZATION_COHORT_EXHAUSTED")


def _generalization_stratum(row):
    """Keep the source draw's answer, operand-pattern and world-shape coverage."""
    return (row["capability"], row.get("answer_kind", "binary"), row["gold"],
            tuple(row.get("operand_truths", ())), row.get("universe_size"))


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
