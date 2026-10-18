"""Active championship ownership within one admitted curriculum epoch.

Historical champion and soup receipts stay in the old state fields. The
epoch owns only fresh perfect winners and their frozen vote entitlements.
This module never reads tensors, trains a student, or changes an optimizer.
"""
from __future__ import annotations

from copy import deepcopy

from .championship_policy import cross_origin_takeover


def active_frontier(epoch: dict) -> dict:
    """Adapt one-owner-per-capability receipts to existing soup machinery."""
    roles = epoch.get("active_roles", {})
    if not isinstance(roles, dict):
        raise ValueError("CHAMPIONSHIP_EPOCH_ACTIVE_ROLES_INVALID")
    if any(not isinstance(item, dict) or item.get("capability") != cap
           for cap, item in roles.items()):
        raise ValueError("CHAMPIONSHIP_EPOCH_ACTIVE_ROLE_DRIFT")
    return {item["rubric"] + ":" + cap: item for cap, item in roles.items()}


def _grade_caps(course_grades, grade):
    result = tuple(course_grades[grade])
    if not result or len(result) != len(set(result)):
        raise ValueError("CHAMPIONSHIP_EPOCH_INVALID_GRADE")
    return result


def needed_incumbents(epoch: dict, *, grades: dict, scores: dict) -> dict:
    """Identify only checkpoints needed for a potential qualifying challenge."""
    roles = epoch.get("active_roles", {})
    origin = epoch["introduced_grade"]
    baseline = epoch["baseline"]
    mastered = sum(v["correct"] == v["total"] for v in scores.values())
    needed = {}
    for grade in grades:
        caps = _grade_caps(grades, grade)
        if grade == origin:
            for cap in caps:
                if cap not in scores or scores[cap]["correct"] != scores[cap]["total"]:
                    continue
                prior = roles.get(cap)
                if prior is not None and mastered > prior["breadth"]:
                    pointer = prior["checkpoint"]
                    needed[pointer["sha256"]] = pointer
        elif all(cap in scores and scores[cap]["correct"] == scores[cap]["total"]
                 for cap in caps):
            for cap in caps:
                pointer = roles.get(cap, {}).get("checkpoint", baseline)
                needed[pointer["sha256"]] = pointer
    return needed


def advance_epoch(epoch: dict, *, grades: dict, challenger_exam: dict,
                  incumbent_exams: dict) -> tuple[dict, tuple[str, ...], tuple[dict, ...]]:
    """Apply earned changes only after source-comparable whole-student scoring."""
    scores = challenger_exam["scores"]
    pointer = challenger_exam["checkpoint"]
    mastered = tuple(sorted(cap for cap, score in scores.items()
                            if score["correct"] == score["total"]))
    breadth = len(mastered)
    updated = deepcopy(epoch)
    roles = updated.setdefault("active_roles", {})
    updated.setdefault("active_grade_soups", {})
    changes, decisions = [], []
    origin = epoch["introduced_grade"]

    def record(capability):
        roles[capability] = {
            "rubric": challenger_exam["rubric_sha256"],
            "capability": capability,
            "cohort_sha256": challenger_exam["cohort_sha256"],
            "correct": scores[capability]["correct"],
            "total": scores[capability]["total"],
            "breadth": breadth,
            "perfect_capabilities": list(mastered),
            "checkpoint": dict(pointer),
            "evaluation_id": (
                "championship-epoch/" + challenger_exam["cohort_sha256"] +
                "/" + pointer["sha256"]),
        }
        changes.append(capability)

    # Current-origin roles keep ordinary strictly-greater simultaneous breadth.
    for cap in _grade_caps(grades, origin):
        if cap not in scores or scores[cap]["correct"] != scores[cap]["total"]:
            continue
        prior = roles.get(cap)
        if prior is not None:
            if prior["checkpoint"]["sha256"] == pointer["sha256"] or (
                    breadth <= prior["breadth"]):
                continue
            incumbent = incumbent_exams.get(prior["checkpoint"]["sha256"])
            if incumbent is None or (
                    incumbent["cohort_sha256"] != challenger_exam["cohort_sha256"] or
                    incumbent["rubric_sha256"] != challenger_exam["rubric_sha256"] or
                    incumbent["assessment_scope_sha256"] !=
                    challenger_exam["assessment_scope_sha256"] or
                    set(incumbent["scores"]) != set(scores) or
                    any(incumbent["scores"][c]["total"] != scores[c]["total"]
                        for c in scores)):
                raise ValueError("CHAMPIONSHIP_EPOCH_SAME_COHORT_REQUIRED")
            incumbent_breadth = sum(
                v["correct"] == v["total"] for v in incumbent["scores"].values())
            if breadth <= incumbent_breadth:
                continue
        record(cap)

    # Other grades cannot change one role at a time: require the entire
    # target grade perfect and outrank every displaced role owner school-wide.
    for grade in grades:
        if grade == origin:
            continue
        caps = _grade_caps(grades, grade)
        if not all(cap in scores and scores[cap]["correct"] == scores[cap]["total"]
                   for cap in caps):
            continue
        owners = {cap: roles.get(cap, {}).get(
            "checkpoint", epoch["baseline"])["sha256"] for cap in caps}
        verdict = cross_origin_takeover(
            grade_capabilities=caps, admitted_capabilities=tuple(scores),
            active_role_owners=owners, challenger_exam=challenger_exam,
            incumbent_exams={sha: incumbent_exams[sha] for sha in set(owners.values())})
        decisions.append({"grade": grade, **verdict})
        if verdict["decision"] == "ELIGIBLE":
            for cap in caps:
                record(cap)
    return updated, tuple(changes), tuple(decisions)
