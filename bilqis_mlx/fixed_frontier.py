"""Monotonic screening against the current immutable whole-school exam frontier."""
from __future__ import annotations

import json
from pathlib import Path

from .generated_assessment import make_cohort


def _valid_sha(value) -> bool:
    return (isinstance(value, str) and len(value) == 64 and
            all(char in "0123456789abcdef" for char in value))


def _load_verified_rows(run_dir: Path, exam: dict) -> tuple[dict, ...]:
    sha = exam.get("cohort_sha256")
    if (not _valid_sha(sha) or
            exam.get("cohort_file") != f"cohorts/{sha}.json"):
        raise ValueError("FIXED_FRONTIER_UNBOUND_EXAM_COHORT")
    path = Path(run_dir) / exam["cohort_file"]
    if path.parent.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("FIXED_FRONTIER_UNSAFE_COHORT_PATH")
    stored = json.loads(path.read_text(encoding="utf-8"))
    required = ("cohort_sha256", "generator_version", "schema", "seed", "rows")
    if any(key not in stored for key in required):
        raise ValueError("FIXED_FRONTIER_COHORT_METADATA_MISSING")
    cohort = make_cohort(
        stored["rows"], generator_version=stored["generator_version"],
        seed=stored["seed"], rubric_version=stored["schema"])
    if stored["cohort_sha256"] != sha or cohort.digest != sha:
        raise ValueError("FIXED_FRONTIER_COHORT_CONTENT_DRIFT")
    rows = tuple(cohort.rows)
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("FIXED_FRONTIER_DUPLICATE_ROW")
    return rows


def _reconstruct_parent(rows: tuple[dict, ...], exam: dict) -> dict[str, str]:
    by_id = {row["id"]: row for row in rows}
    misses = exam.get("misses_for_teacher") or ()
    if not isinstance(misses, list):
        raise ValueError("FIXED_FRONTIER_MISSES_INVALID")
    wrong = {}
    for miss in misses:
        row = by_id.get(miss.get("id"))
        predicted = miss.get("predicted")
        if (row is None or miss.get("capability") != row["capability"] or
                miss.get("gold") != row["gold"] or
                not isinstance(predicted, str) or not predicted or
                predicted == row["gold"] or miss["id"] in wrong):
            raise ValueError("FIXED_FRONTIER_MISS_DRIFT")
        wrong[miss["id"]] = predicted
    return {
        row["id"]: wrong.get(row["id"], row["gold"])
        for row in rows
    }


def _scores(rows, predictions):
    result = {}
    for row in rows:
        entry = result.setdefault(
            row["capability"], {"correct": 0, "total": 0})
        entry["total"] += 1
        entry["correct"] += int(predictions[row["id"]] == row["gold"])
    return result


def load_frontier(run_dir: Path, receipt: dict) -> tuple[tuple[dict, ...], dict[str, str]]:
    """Load fixed rows and reconstruct the current parent's exact predictions."""
    exam = receipt.get("last_exam") or {}
    if not exam.get("scores") or exam.get("cohort_sha256") is None:
        return (), {}
    rows = _load_verified_rows(run_dir, exam)
    parent = _reconstruct_parent(rows, exam)
    if _scores(rows, parent) != exam["scores"]:
        raise ValueError("FIXED_FRONTIER_RECONSTRUCTED_SCORE_DRIFT")
    return rows, parent


def screen_frontier(rows, parent_predictions, candidate_predictions,
                    cohort_sha256: str) -> dict:
    """Report repairs anywhere and veto-worthy regressions anywhere."""
    if not _valid_sha(cohort_sha256):
        raise ValueError("FIXED_FRONTIER_COHORT_DIGEST_INVALID")
    required = {row["id"] for row in rows}
    if (not rows or required - parent_predictions.keys() or
            required - candidate_predictions.keys()):
        raise ValueError("FIXED_FRONTIER_MISSING_PAIRED_PREDICTION")
    regressions, repaired, grades = [], [], {}
    before_correct = after_correct = 0
    for row in rows:
        identity, gold = row["id"], row["gold"]
        old = parent_predictions[identity] == gold
        new = candidate_predictions[identity] == gold
        before_correct += int(old)
        after_correct += int(new)
        if old and not new:
            regressions.append({"id": identity, "capability": row["capability"]})
        elif not old and new:
            repaired.append({"id": identity, "capability": row["capability"]})
        grade = row["capability"].partition(".")[0]
        entry = grades.setdefault(
            grade, {"before": 0, "after": 0, "total": 0})
        entry["before"] += int(old)
        entry["after"] += int(new)
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
