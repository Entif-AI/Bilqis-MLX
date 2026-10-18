"""Monotonic screening against the current immutable whole-school exam frontier."""
from __future__ import annotations

import json
from pathlib import Path

from .generated_assessment import make_cohort


def _valid_sha(value) -> bool:
    return (isinstance(value, str) and len(value) == 64 and
            all(char in "0123456789abcdef" for char in value))


def load_frontier(run_dir: Path, receipt: dict, *, parent_sha256: str,
                  parent_optimizer_step: int) -> tuple[tuple[dict, ...], dict[str, str]]:
    """Load the current fixed cohort and reconstruct the retained parent's outputs.

    The saved exam stores only misses. Every other fixed row was correct by
    definition; recomputing capability totals proves that reconstruction before
    it is used as an admission reference.
    """
    exam = receipt.get("last_exam") or {}
    scores = exam.get("scores")
    sha = exam.get("cohort_sha256")
    if not scores or sha is None:
        return (), {}
    if (exam.get("student_sha256") != parent_sha256 or
            exam.get("optimizer_step") != parent_optimizer_step):
        raise ValueError("FIXED_FRONTIER_PARENT_IDENTITY_DRIFT")
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
        raise ValueError("FIXED_FRONTIER_COHORT_METADATA_DRIFT")
    cohort = make_cohort(
        stored["rows"], generator_version=stored["generator_version"],
        seed=stored["seed"], rubric_version=stored["schema"])
    if cohort.digest != sha:
        raise ValueError("FIXED_FRONTIER_COHORT_CONTENT_DRIFT")

    rows = tuple(cohort.rows)
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("FIXED_FRONTIER_DUPLICATE_ROW")
    by_id = {row["id"]: row for row in rows}
    misses = exam.get("misses_for_teacher") or ()
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
    for entry in grades.values():
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
    }
