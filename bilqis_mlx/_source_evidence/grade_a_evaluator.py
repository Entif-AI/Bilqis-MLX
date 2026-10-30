"""Fixed-item Grade A scoring, independent of any neural optimizer.

Only scores predictions against the pinned source-derived examination rows.
This evaluator does not itself authorize a curriculum, construct NI morphology,
or grant model-training permission.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bilqis_mlx.learning.champions import Checkpoint
from .curriculum import Course
from .grade_a_manifest import verify_manifest
from bilqis_mlx.curriculum.scheduler import Assessment, Score


def capability_scores(manifest: dict, course: Course,
                      predictions: dict[str, str]) -> dict[str, Score]:
    """Evaluate a complete in-memory candidate before writing its archive."""
    rows = manifest["examination_rows"]
    ids = [row["id"] for row in rows]
    if (not isinstance(predictions, dict) or len(ids) != len(set(ids))
            or set(predictions) != set(ids)):
        raise ValueError("GRADE_A_EVALUATOR_INCOMPLETE_OR_UNKNOWN_EXAM_ITEMS")
    if any(predictions[i] not in ("TRUE", "FALSE") for i in ids):
        raise ValueError("GRADE_A_EVALUATOR_WRONG_ANSWER_TYPE")
    found = {}
    for cap in course.grades[0].capabilities:
        group = [r for r in rows if r["capability"] == cap.id]
        expected = dict(course.grades[0].exam_item_counts)[cap.id]
        if len(group) != expected:
            raise ValueError("GRADE_A_EVALUATOR_GRADE_COUNT_DRIFT")
        found[cap.id] = Score(sum(predictions[r["id"]] == r["gold"]
                                  for r in group), len(group))
    return found


def score_predictions(manifest: dict, course: Course, checkpoint: Checkpoint,
                      predictions: dict[str, str], *, legacy_root: Path,
                      source_checkpoint: Path) -> Assessment:
    """Require one candidate checkpoint and exactly all 72 sealed exam IDs."""
    verified = verify_manifest(manifest, legacy_root, source_checkpoint)
    from .grade_a_probe import candidate_course
    from .grade_a_release import accepted_grade_a
    candidate = candidate_course()
    if course not in (candidate, accepted_grade_a(manifest)):
        raise ValueError("GRADE_A_EVALUATOR_NOT_PINNED_PROPOSAL_OR_ACCEPTED_RELEASE")
    if not checkpoint.model_and_native_adamw:
        raise ValueError("GRADE_A_EVALUATOR_REQUIRES_WHOLE_STUDENT_AND_OPTIMIZER")
    by_capability = capability_scores(manifest, course, predictions)
    evaluation = {
        "manifest_sha256": manifest["manifest_sha256"],
        "rubric": verified["exam_rubric_sha256"],
        "checkpoint_sha256": checkpoint.sha256,
        "optimizer_step": checkpoint.optimizer_step,
        "predictions": sorted(predictions.items()),
    }
    evidence_id = hashlib.sha256(
        json.dumps(evaluation, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return Assessment(
        checkpoint_sha256=checkpoint.sha256,
        optimizer_step=checkpoint.optimizer_step,
        course_digest=course.digest(),
        rubric_digest=verified["exam_rubric_sha256"],
        scores=by_capability,
        evaluation_id="candidate-grade-a-source-evaluator/" + evidence_id,
    )
