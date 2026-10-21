"""Re-measure immutable frontier questions at the current retained parent."""
from __future__ import annotations

import bilqis_mlx.learning.student_ops as _learning_student_ops
import bilqis_mlx.runtime.checkpoints as _runtime_checkpoints
import bilqis_mlx.runtime.release_adoption as _runtime_release_adoption
import bilqis_mlx.runtime.state as _runtime_state
import dataclasses as _dataclasses


def _refresh_fixed_frontier(mx, run_dir, receipt, course, parameters, optimizer,
                            *, persist=True):
    """Re-measure preserved questions when a durable retained parent changes."""
    from bilqis_mlx.fixed_frontier import (frontier_exam, load_frontier_cohort,
                                 refresh_frontier_exam)
    exam = frontier_exam(receipt)
    if not exam.get("scores") or not exam.get("cohort_sha256"):
        return receipt
    school = _runtime_state._state_from_json(receipt["school"], _runtime_release_adoption._schedule_for_receipt(run_dir, receipt, course))
    checkpoint = _dataclasses.asdict(school.current_student)
    if (exam.get("student_sha256") == checkpoint["sha256"] and
            exam.get("optimizer_step") == checkpoint["optimizer_step"]):
        return receipt
    if int(optimizer.state["step"].item()) != checkpoint["optimizer_step"]:
        raise ValueError("FIXED_FRONTIER_NATIVE_PARENT_STEP_DRIFT")
    cohort = load_frontier_cohort(run_dir, exam)
    predictions = _learning_student_ops._predictions(mx, parameters, list(cohort.rows),
                               receipt["config"], receipt["answer_ids"])
    updated = {**receipt, "fixed_frontier_exam": refresh_frontier_exam(
        run_dir, exam, checkpoint=checkpoint, predictions=predictions)}
    if persist:
        updated = _runtime_checkpoints._advance(run_dir, updated, school, persist=False)
    event = {"event": "SCHOOL_FIXED_FRONTIER_PARENT_REFRESHED",
             "generation": updated["generation"],
             "student_sha256": checkpoint["sha256"],
             "optimizer_step": checkpoint["optimizer_step"],
             "cohort_sha256": cohort.digest,
             "source_student_sha256": exam.get("student_sha256"),
             "scores": updated["fixed_frontier_exam"]["scores"],
             "actual_neural_updates": 0}
    if not persist:
        updated["_pending_visit_events"] = [
            *updated.get("_pending_visit_events", ()), event]
        return updated
    updated = _runtime_checkpoints._persist(run_dir, _runtime_checkpoints._with_delivery_outbox(updated, (event,)))
    _runtime_checkpoints._reconcile_delivery_outbox(run_dir, updated)
    return updated
