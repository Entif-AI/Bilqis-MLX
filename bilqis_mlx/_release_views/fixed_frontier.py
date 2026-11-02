"""Monotonic screening against the current immutable whole-school exam frontier."""
from __future__ import annotations

import json
from pathlib import Path

from .generated_assessment import (
    EXECUTABLE_COHORT_SCHEMA, score, verify_stored_cohort,
)

_COHORT_METADATA_DRIFT = "FIXED_FRONTIER_COHORT_METADATA_DRIFT"


def _valid_sha(value) -> bool:
    return (isinstance(value, str) and len(value) == 64 and
            all(char in "0123456789abcdef" for char in value))


def load_frontier_cohort(run_dir: Path, exam: dict):
    """Verify and load one immutable cohort referenced by an exam receipt."""
    sha = exam.get("cohort_sha256")
    if sha is None:
        return None
    if (not _valid_sha(sha) or
            exam.get("cohort_file") != f"cohorts/{sha}.json"):
        raise ValueError("FIXED_FRONTIER_UNBOUND_EXAM_COHORT")
    path = Path(run_dir) / exam["cohort_file"]
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("FIXED_FRONTIER_UNSAFE_COHORT_PATH")
    stored = json.loads(path.read_text(encoding="utf-8"))
    if (stored.get("cohort_sha256") != sha or
            not stored.get("generator_version") or not stored.get("schema") or
            type(stored.get("seed")) is not int):
        raise ValueError(_COHORT_METADATA_DRIFT)
    try:
        cohort = verify_stored_cohort(
            stored, sha,
            expected_rubric_sha256=exam.get("rubric_sha256"),
            expected_factory_release_sha256=exam.get(
                "factory_release_sha256"))
    except ValueError as exc:
        if str(exc) == "STORED_COHORT_CONTENT_DRIFT":
            raise ValueError("FIXED_FRONTIER_COHORT_CONTENT_DRIFT") from exc
        raise ValueError(_COHORT_METADATA_DRIFT) from exc
    return cohort


def rebaseline_frontier_exam(run_dir: Path, source_exam: dict, *, checkpoint: dict,
                             predictions: dict, assessment_grade: str | None = None,
                             grade_exam_epoch: int | None = None) -> dict:
    """Bind a preserved cohort to a newly measured, function-preserving parent."""
    cohort = load_frontier_cohort(run_dir, source_exam)
    if cohort is None:
        raise ValueError("FIXED_FRONTIER_REBASELINE_COHORT_REQUIRED")
    measured = score(cohort, predictions, checkpoint)
    source_scores = source_exam.get("scores")
    if isinstance(source_scores, dict) and measured["scores"] != source_scores:
        raise ValueError("FIXED_FRONTIER_REBASELINE_SCORE_DRIFT")
    pointer = {
        "assessment_grade": assessment_grade or source_exam.get("assessment_grade"),
        "grade_exam_epoch": (grade_exam_epoch if grade_exam_epoch is not None
                             else source_exam.get("grade_exam_epoch")),
        "exam_plane": "FIXED_FRONTIER_REBASELINE",
        "source_exam_plane": source_exam.get(
            "source_exam_plane", source_exam.get("exam_plane")),
        "assessment_scope_sha256": source_exam.get("assessment_scope_sha256"),
        "evaluation_id": "fixed-frontier-rebaseline/" + cohort.digest + "/" +
                         checkpoint["sha256"],
        "exam_rubric_sha256": source_exam.get("exam_rubric_sha256"),
        "cohort_sha256": cohort.digest,
        "cohort_file": source_exam["cohort_file"],
        "cohort_seed": cohort.seed,
        "generator_version": cohort.generator_version,
        "misses_for_teacher": list(measured["misses_for_teacher"]),
        "student_sha256": checkpoint["sha256"],
        "optimizer_step": checkpoint["optimizer_step"],
        "scores": measured["scores"],
        "rebaselined_from_student_sha256": source_exam.get("student_sha256"),
        "rebaseline_reason": "APPEND_ONLY_SEMANTIC_GRAPH_GROWTH",
    }
    if source_exam.get("schema") == EXECUTABLE_COHORT_SCHEMA:
        required = (
            "factory_release_sha256", "capabilities", "rubric_sha256",
            "source_sha256",
        )
        if any(source_exam.get(key) is None for key in required):
            raise ValueError("FIXED_FRONTIER_V2_POINTER_INCOMPLETE")
        pointer.update({
            "schema": EXECUTABLE_COHORT_SCHEMA,
            **{key: source_exam[key] for key in required},
        })
    return pointer


def frontier_exam(receipt: dict) -> dict:
    """Select current-parent evidence without replacing routine exam history."""
    original = receipt.get("last_exam") or {}
    refreshed = receipt.get("fixed_frontier_exam")
    if refreshed is None:
        return original
    bindings = ("cohort_sha256", "exam_rubric_sha256", "assessment_scope_sha256",
                "assessment_grade", "grade_exam_epoch")
    if any(refreshed.get(key) != original.get(key) for key in bindings):
        raise ValueError("FIXED_FRONTIER_SOURCE_EXAM_DRIFT")
    return refreshed


def refresh_frontier_exam(run_dir: Path, source_exam: dict, *, checkpoint: dict,
                          predictions: dict) -> dict:
    """Measure a retained parent on the unchanged, verified source cohort."""
    load_frontier(run_dir, {"last_exam": source_exam},
                  parent_sha256=source_exam.get("student_sha256"),
                  parent_optimizer_step=source_exam.get("optimizer_step"))
    cohort = load_frontier_cohort(run_dir, source_exam)
    measured = score(cohort, predictions, checkpoint)
    keys = ("cohort_sha256", "cohort_file", "cohort_seed", "generator_version",
            "exam_rubric_sha256", "assessment_scope_sha256", "assessment_grade",
            "grade_exam_epoch")
    return {**{key: source_exam[key] for key in keys if key in source_exam},
            "exam_plane": "FIXED_FRONTIER_CURRENT_PARENT",
            "student_sha256": checkpoint["sha256"],
            "optimizer_step": checkpoint["optimizer_step"],
            "scores": measured["scores"],
            "misses_for_teacher": list(measured["misses_for_teacher"]),
            "source_student_sha256": source_exam.get("student_sha256")}


def load_frontier(run_dir: Path, receipt: dict, *, parent_sha256: str,
                  parent_optimizer_step: int) -> tuple[tuple[dict, ...], dict[str, str]]:
    """Load the current fixed cohort and reconstruct the retained parent's outputs."""
    exam = frontier_exam(receipt)
    scores = exam.get("scores")
    if not scores or exam.get("cohort_sha256") is None:
        return (), {}
    if (exam.get("student_sha256") != parent_sha256 or
            exam.get("optimizer_step") != parent_optimizer_step):
        raise ValueError("FIXED_FRONTIER_PARENT_IDENTITY_DRIFT")
    cohort = load_frontier_cohort(run_dir, exam)

    rows = tuple(cohort.rows)
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("FIXED_FRONTIER_DUPLICATE_ROW")
    by_id = {row["id"]: row for row in rows}
    misses = exam.get("misses_for_teacher")
    if misses is None:
        misses = []
    if not isinstance(misses, list):
        raise ValueError("FIXED_FRONTIER_MISSES_INVALID")
    miss_predictions = {}
    for miss in misses:
        row = by_id.get(miss.get("id"))
        predicted = miss.get("predicted")
        if (row is None or miss.get("capability") != row["capability"] or
                miss.get("gold") != row["gold"] or
                not isinstance(predicted, str) or not predicted or
                predicted == row["gold"] or miss["id"] in miss_predictions):
            raise ValueError("FIXED_FRONTIER_MISS_DRIFT")
        miss_predictions[miss["id"]] = predicted

    parent = {
        row["id"]: miss_predictions.get(row["id"], row["gold"])
        for row in rows
    }
    measured = {}
    for row in rows:
        entry = measured.setdefault(
            row["capability"], {"correct": 0, "total": 0})
        entry["total"] += 1
        entry["correct"] += int(parent[row["id"]] == row["gold"])
    if measured != scores:
        raise ValueError("FIXED_FRONTIER_RECONSTRUCTED_SCORE_DRIFT")
    return rows, parent


def screen_frontier(rows, parent_predictions, candidate_predictions,
                    cohort_sha256: str) -> dict:
    """Require monotonic correctness on every previously-correct fixed row."""
    if not _valid_sha(cohort_sha256):
        raise ValueError("FIXED_FRONTIER_COHORT_DIGEST_INVALID")
    required = {row["id"] for row in rows}
    if (not rows or required - parent_predictions.keys() or
            required - candidate_predictions.keys()):
        raise ValueError("FIXED_FRONTIER_MISSING_PAIRED_PREDICTION")
    regressions, repaired = [], []
    grades = {}
    capabilities = {}
    before_correct = after_correct = 0
    for row in rows:
        identity, gold = row["id"], row["gold"]
        old, new = parent_predictions[identity], candidate_predictions[identity]
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError("FIXED_FRONTIER_INVALID_PREDICTION")
        old_ok, new_ok = old == gold, new == gold
        before_correct += int(old_ok)
        after_correct += int(new_ok)
        if old_ok and not new_ok:
            regressions.append({
                "id": identity, "capability": row["capability"]})
        elif not old_ok and new_ok:
            repaired.append({
                "id": identity, "capability": row["capability"]})
        grade = row["capability"].partition(".")[0]
        entry = grades.setdefault(
            grade, {"before": 0, "after": 0, "total": 0})
        entry["before"] += int(old_ok)
        entry["after"] += int(new_ok)
        entry["total"] += 1
        capability_entry = capabilities.setdefault(
            row["capability"], {"before": 0, "after": 0, "total": 0})
        capability_entry["before"] += int(old_ok)
        capability_entry["after"] += int(new_ok)
        capability_entry["total"] += 1
    for entry in grades.values():
        entry["net_correct_delta"] = entry["after"] - entry["before"]
    for entry in capabilities.values():
        entry["net_correct_delta"] = entry["after"] - entry["before"]
    return {
        "status": "MEASURED",
        "cohort_sha256": cohort_sha256,
        "rows": len(rows),
        "before_correct": before_correct,
        "after_correct": after_correct,
        "net_correct_delta": after_correct - before_correct,
        "regressions": regressions,
        "repaired": repaired,
        "grades": grades,
        "capabilities": capabilities,
    }
