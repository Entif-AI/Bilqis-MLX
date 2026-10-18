"""Neural-inert trial of active-mentor reset at a new curriculum grade.

Historical champions and soups remain archived elsewhere unchanged. These
functions only *plan* an active adviser roster; they never clone weights,
update AdamW, declare graduation or install a new human training policy.
The caller must independently verify checkpoint bundles and graph binding.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json


SCHEMA = "bilqis.mlx.mentor-epoch-trial/v1"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(
        symbol in "0123456789abcdef" for symbol in value)


def _pointer(pointer):
    if (not isinstance(pointer, dict) or not _sha(pointer.get("sha256")) or
            not isinstance(pointer.get("filename"), str) or
            len(pointer["filename"].split("/")) != 2 or
            pointer["filename"].split("/")[0] != "bundles" or
            pointer["filename"].split("/")[1] in (".", "..", "") or
            type(pointer.get("optimizer_step")) is not int or
            pointer["optimizer_step"] < 0 or
            pointer.get("model_and_native_adamw") is not True):
        raise ValueError("MENTOR_EPOCH_WHOLE_STUDENT_OWN_ADAMW_REQUIRED")
    return dict(pointer)


def _scores(scores):
    if not isinstance(scores, dict) or not scores:
        raise ValueError("MENTOR_EPOCH_INCOMPLETE_SCORES")
    for cap, value in scores.items():
        if (not isinstance(cap, str) or not cap or
                not isinstance(value, dict) or
                type(value.get("correct")) is not int or
                type(value.get("total")) is not int or
                not 0 <= value["correct"] <= value["total"] or
                value["total"] < 1):
            raise ValueError("MENTOR_EPOCH_INVALID_SOURCE_SCORE")
    return scores


def begin_epoch(*, previous_graduate: dict, admitted_baseline: dict,
                introduced_grade: str, source_graph_sha256: str,
                previous_capabilities: tuple[str, ...],
                previous_graduation_exam: dict) -> dict:
    """Describe a frozen post-admission baseline, not fabricate a new soup.

    The previous graduation exam must belong to one complete source-scored
    student; the post-admission reference may differ after append-only
    vocabulary extension, but remains an intact, separately bound checkpoint.
    """
    graduate = _pointer(previous_graduate)
    baseline = _pointer(admitted_baseline)
    caps = tuple(previous_capabilities)
    if (not introduced_grade or not _sha(source_graph_sha256) or
            not caps or len(set(caps)) != len(caps) or
            any(not isinstance(cap, str) or
                cap.partition(".")[0] == introduced_grade for cap in caps) or
            baseline["optimizer_step"] < graduate["optimizer_step"]):
        raise ValueError("MENTOR_EPOCH_INVALID_GRADE_BOUNDARY")
    exam = previous_graduation_exam
    if (not isinstance(exam, dict) or
            exam.get("checkpoint_sha256") != graduate["sha256"] or
            not _sha(exam.get("cohort_sha256")) or
            not _sha(exam.get("rubric_sha256")) or
            set(_scores(exam.get("scores"))) != set(caps) or
            any(exam["scores"][cap]["correct"] != exam["scores"][cap]["total"]
                for cap in caps)):
        raise ValueError("MENTOR_EPOCH_COMPLETE_PREVIOUS_GRADUATION_REQUIRED")
    return {"schema": SCHEMA, "introduced_grade": introduced_grade,
            "source_graph_sha256": source_graph_sha256,
            "previous_capabilities": list(caps),
            "previous_graduate": graduate, "baseline": baseline,
            "baseline_roles": {cap: baseline["sha256"] for cap in sorted(caps)},
            "earned_role_votes_at_reset": 0,
            "previous_graduation_exam_sha256": _digest(exam),
            "qualified": [], "historical_advisers_remain_archived": True}


def active_adviser_checkpoints(epoch: dict, *, cohort_sha256: str | None = None,
                               scope_sha256: str | None = None,
                               rubric_sha256: str | None = None) -> tuple[dict, ...]:
    """One baseline plus at most one latest qualified new active adviser.

    Never multiply a checkpoint because it once owned several roles. This is
    an experimental roster; original soup recipes and votes are not rewritten.
    """
    if epoch.get("schema") != SCHEMA:
        raise ValueError("MENTOR_EPOCH_UNKNOWN_SCHEMA")
    baseline = _pointer(epoch["baseline"])
    qualified = epoch.get("qualified", [])
    if not isinstance(qualified, list):
        raise ValueError("MENTOR_EPOCH_INVALID_QUALIFIED_HISTORY")
    if any(value is not None and not _sha(value)
           for value in (cohort_sha256, scope_sha256, rubric_sha256)):
        raise ValueError("MENTOR_EPOCH_INVALID_ADVISER_SCOPE")
    eligible = [entry for entry in qualified
                if (cohort_sha256 is None or entry["cohort_sha256"] == cohort_sha256)
                and (scope_sha256 is None or entry["scope_sha256"] == scope_sha256)
                and (rubric_sha256 is None or entry["rubric_sha256"] == rubric_sha256)]
    if not eligible:
        return (baseline,)
    latest = _pointer(eligible[-1]["checkpoint"])
    return (baseline,) if latest["sha256"] == baseline["sha256"] else (baseline, latest)


def reference_checkpoints(epoch: dict) -> tuple[dict, ...]:
    """Preserve *all* referenced whole models, not only the latest adviser.

    A mentor can cease to qualify on a new cohort without becoming unowned
    checkpoint data. Archive custody and active teaching eligibility differ.
    """
    active_adviser_checkpoints(epoch)
    pointers = [_pointer(epoch["previous_graduate"]), _pointer(epoch["baseline"])]
    pointers.extend(_pointer(item["checkpoint"]) for item in epoch["qualified"])
    unique = {}
    for pointer in pointers:
        former = unique.setdefault(pointer["sha256"], pointer)
        if former != pointer:
            raise ValueError("MENTOR_EPOCH_CHECKPOINT_POINTER_CONFLICT")
    return tuple(unique.values())


def qualify_candidate(epoch: dict, candidate: dict, baseline_exam: dict,
                      candidate_exam: dict, *, mature_loss_budget: int) -> dict:
    """Trial-only mentor eligibility, not student admission or graduation.

    Both complete examinations must use *identical* source questions, graph,
    rubric and assessment scope. The explicit tolerance is a policy input,
    not a hidden zero-forgetting mandate or an optimizer-level candidate gate.
    """
    active_adviser_checkpoints(epoch)
    pointer = _pointer(candidate)
    if type(mature_loss_budget) is not int or mature_loss_budget < 0:
        raise ValueError("MENTOR_EPOCH_INVALID_MATURE_LOSS_POLICY")
    common = ("cohort_sha256", "rubric_sha256", "assessment_scope_sha256",
              "source_graph_sha256")
    if (not isinstance(baseline_exam, dict) or
            not isinstance(candidate_exam, dict) or
            any(not _sha(baseline_exam.get(k)) or
                baseline_exam[k] != candidate_exam.get(k) for k in common) or
            baseline_exam["source_graph_sha256"] != epoch["source_graph_sha256"] or
            baseline_exam.get("checkpoint_sha256") != epoch["baseline"]["sha256"] or
            candidate_exam.get("checkpoint_sha256") != pointer["sha256"] or
            pointer["sha256"] == epoch["baseline"]["sha256"]):
        raise ValueError("MENTOR_EPOCH_MISMATCHED_EXAMINATION")
    before, after = _scores(baseline_exam.get("scores")), _scores(candidate_exam.get("scores"))
    prior = set(epoch["previous_capabilities"])
    current = {name for name in before if name.partition(".")[0] ==
               epoch["introduced_grade"]}
    if (not current or set(before) != set(after) or
            not prior <= set(before) or
            any(before[name]["total"] != after[name]["total"] for name in before) or
            any(name not in prior | current for name in before)):
        raise ValueError("MENTOR_EPOCH_INCOMPLETE_PAIRED_SCOPE")
    old_losses = {name: before[name]["correct"] - after[name]["correct"]
                  for name in prior if before[name]["correct"] > after[name]["correct"]}
    new_gain = sum(after[name]["correct"] - before[name]["correct"] for name in current)
    total_gain = sum(after[name]["correct"] - before[name]["correct"] for name in before)
    if new_gain <= 0:
        decision = "HOLD_NO_NEW_GRADE_GAIN"
    elif max(old_losses.values(), default=0) > mature_loss_budget:
        decision = "HOLD_MATURE_LOSS"
    elif total_gain <= 0:
        decision = "HOLD_NO_CUMULATIVE_GAIN"
    elif any(item["cohort_sha256"] == baseline_exam["cohort_sha256"] and
             item["scope_sha256"] == baseline_exam["assessment_scope_sha256"] and
             item["rubric_sha256"] == baseline_exam["rubric_sha256"] and
             item["cumulative_correct_gain"] >= total_gain
             for item in epoch["qualified"]):
        decision = "HOLD_NO_BETTER_SAME_SCOPE_REFERENCE"
    else:
        decision = "QUALIFIED"
    updated = deepcopy(epoch)
    if decision == "QUALIFIED" and not any(
            item["checkpoint"]["sha256"] == pointer["sha256"]
            for item in updated["qualified"]):
        updated["qualified"].append({
            "checkpoint": pointer, "scope_sha256": baseline_exam["assessment_scope_sha256"],
            "cohort_sha256": baseline_exam["cohort_sha256"],
            "rubric_sha256": baseline_exam["rubric_sha256"],
            "cumulative_correct_gain": total_gain,
            "new_grade_correct_gain": new_gain,
            "paired_evidence_sha256": _digest([baseline_exam, candidate_exam])})
    return {"decision": decision, "new_grade_correct_gain": new_gain,
            "cumulative_correct_gain": total_gain, "mature_losses": old_losses,
            "epoch": updated, "student_or_optimizer_mutated": False}
