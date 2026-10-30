"""Neural-inert repair of checkpoint-bound runtime metadata."""
from __future__ import annotations

import bilqis_mlx.curriculum.scheduler as _curriculum_scheduler
import bilqis_mlx.generated_assessment as _bilqis_mlx_generated_assessment
import bilqis_mlx.learning.learning_experiment as _learning_learning_experiment
import bilqis_mlx.learning.stagnation_control as _learning_stagnation_control
import bilqis_mlx.learning.whole_student_retention as _learning_whole_student_retention
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import copy as _copy
import dataclasses as _dataclasses
import json as _json

SHA256_HEX_LENGTH = 64
CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CUSTODY_DRIFT = "CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CUSTODY_DRIFT"
CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_IDENTITY_DRIFT = "CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_IDENTITY_DRIFT"
CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_COHORT_MISSING = "CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_COHORT_MISSING"
CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CONTENT_DRIFT = "CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CONTENT_DRIFT"


def _require_championship_source_context_custody(condition: bool) -> None:
    if not condition:
        raise ValueError(CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CUSTODY_DRIFT)


def _affected_championship_source_context(run_dir, epoch) -> set[str]:
    affected = set()
    for capability, role in epoch["active_roles"].items():
        evidence = (
            *role.get("qualification_witnesses", ()),
            *role.get("surviving_battery", ()),
        )
        for item in evidence:
            sha = item.get("cohort_sha256")
            assessment_rubric = item.get("rubric_sha256")
            source_oracle = item.get("source_oracle_sha256")
            if not all(isinstance(value, str) and len(value) == SHA256_HEX_LENGTH
                       for value in (sha, assessment_rubric, source_oracle)):
                raise ValueError(CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_IDENTITY_DRIFT)
            path = run_dir / "cohorts" / (sha + ".json")
            if path.is_symlink() or not path.is_file():
                raise ValueError(CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_COHORT_MISSING)
            stored = _json.loads(path.read_text())
            _require_championship_source_context_custody(
                stored.get("cohort_sha256") == sha and
                stored.get("source_manifest_sha256") == source_oracle)
            try:
                _bilqis_mlx_generated_assessment.verify_stored_cohort(stored, sha)
            except ValueError as exc:
                raise ValueError(
                    CHAMPIONSHIP_SOURCE_CONTEXT_REPAIR_CONTENT_DRIFT) from exc
            declared_cohort_rubric = item.get("cohort_rubric_sha256")
            if declared_cohort_rubric is not None:
                # A modern witness has a distinct, authenticated source
                # rubric. It is authoritative for its own cohort and cannot
                # be replaced by either the championship title rubric or a
                # later exam's scope. Verify it rather than skipping the row.
                _require_championship_source_context_custody(
                    stored.get("rubric_sha256") == declared_cohort_rubric)
                continue
            if stored.get("rubric_sha256") != assessment_rubric:
                affected.add(capability)
                break
    return affected


def _invalidate_championship_source_context(epoch, affected: set[str]):
    reset = _copy.deepcopy(epoch)
    for capability in sorted(affected):
        prior = reset["active_roles"].pop(capability)
        reset.setdefault("invalidated_active_roles", []).append({
            "capability": capability,
            "reason": "COHORT_SOURCE_RUBRIC_CONTRADICTION",
            "role": prior,
        })
    touched_grades = {cap.partition(".")[0] for cap in affected}
    for grade in sorted(touched_grades):
        prior_soup = reset.get("active_grade_soups", {}).pop(grade, None)
        if prior_soup is not None:
            reset.setdefault("invalidated_active_soups", []).append({
                "grade": grade,
                "reason": "ROLE_SOURCE_CONTRADICTION",
                "active_grade_soup": prior_soup,
            })
    return reset


def _repair_championship_source_context(run_dir, receipt, course):
    """Archive titles minted while cohort-source and assessment rubrics were conflated."""
    epoch = receipt.get("mentor_epoch")
    if not isinstance(epoch, dict) or not epoch.get("active_roles"):
        return receipt

    affected = _affected_championship_source_context(run_dir, epoch)

    if not affected:
        return receipt

    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    history = [*receipt.get("championship_epoch_history", ()), _copy.deepcopy(epoch)]
    # This is a capability-local evidence failure, not a holistic school
    # identity change. Invalidate only the affected title(s) and their grade
    # soup(s). In particular, settled matchups are permanent; clearing that
    # ledger would permit repeated title matches between the same checkpoints.
    reset = _invalidate_championship_source_context(epoch, affected)
    repaired = {
        **receipt,
        "mentor_epoch": reset,
        "championship_epoch_history": history,
    }
    record = _runtime_checkpoints._advance(
        run_dir, repaired, school,
        result=receipt.get("result"), persist=False)
    event = {
        "event": "SCHOOL_CHAMPIONSHIP_SOURCE_CONTEXT_REPAIRED",
        "generation": record["generation"],
        "source_generation": receipt["generation"],
        "student_sha256": school.current_student.sha256,
        "optimizer_step": school.current_student.optimizer_step,
        "invalidated_championship_roles": sorted(affected),
        "archived_prior_epoch": True,
        "preserved_championship_roles": sorted(reset["active_roles"]),
        "preserved_settled_matchups": len(reset.get("settled_matchups", {})),
        "actual_neural_updates": 0,
        "model_and_own_adamw_unchanged": True,
    }
    record = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(record, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, record)
    return record
