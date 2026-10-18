"""Active championship ownership within one admitted curriculum epoch.

Historical champion and soup receipts stay in the old state fields. The
epoch owns only fresh perfect winners and their frozen vote entitlements.
This module never reads tensors, trains a student, or changes an optimizer.
"""
from __future__ import annotations

from copy import deepcopy

from .championship_policy import cross_origin_takeover
from .mentor_epoch import EARNED_ONLY_POLICY, _pointer


def reset_active_championships(epoch: dict, *, student: dict,
                               generation: int) -> tuple[dict, bool]:
    """Metadata-only reset with lossless historical role/soup evidence.

    The current causal student becomes a *non-teaching* reset reference.
    Its optimizer step must be surpassed before future exams can award roles.
    An already reset epoch is returned unchanged, for idempotent preparation.
    """
    candidate = _pointer(student)
    previous = _pointer(epoch["baseline"])
    if (type(generation) is not int or generation < 1 or
            candidate["optimizer_step"] < previous["optimizer_step"]):
        raise ValueError("CHAMPIONSHIP_RESET_INVALID_STUDENT_OR_GENERATION")
    if epoch.get("active_championship_reset") is not None:
        return deepcopy(epoch), False
    updated = deepcopy(epoch)
    archived = {
        "source_generation": generation,
        "starting_student": candidate,
        "active_roles": updated.get("active_roles", {}),
        "active_grade_soups": updated.get("active_grade_soups", {}),
        "qualified": updated.get("qualified", []),
        "baseline_roles": updated.get("baseline_roles", {}),
    }
    updated["superseded_active_championships"] = [
        *updated.get("superseded_active_championships", []), archived]
    updated["active_roles"] = {}
    updated["active_grade_soups"] = {}
    updated["baseline_roles"] = {}
    updated["qualified"] = []
    updated["earned_role_votes_at_reset"] = 0
    updated["guidance_policy"] = EARNED_ONLY_POLICY
    updated["championship_eligibility_after_step"] = candidate["optimizer_step"]
    updated["active_championship_reset"] = {
        "policy": EARNED_ONLY_POLICY,
        "source_generation": generation,
        "student_sha256": candidate["sha256"],
        "optimizer_step": candidate["optimizer_step"],
        "old_active_role_count": len(archived["active_roles"]),
        "old_active_soup_grades": sorted(archived["active_grade_soups"]),
        "preexisting_championships_archived": True,
        "training_or_optimizer_updates": 0,
    }
    return updated, True


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


def _incomplete_grade_decision(grade, capabilities, scores, sha, *, origin):
    missing = [cap for cap in capabilities if cap not in scores]
    if missing:
        return {"grade": grade, "decision": (
            "DEFER_ORIGIN_GRADE_INCOMPLETE" if origin else
            "DEFER_TARGET_GRADE_INCOMPLETE"),
            "missing_capabilities": missing, "candidate_sha256": sha}
    if not origin and any(scores[cap]["correct"] != scores[cap]["total"]
                          for cap in capabilities):
        return {"grade": grade, "decision": "DENY_TARGET_GRADE_NOT_PERFECT",
                "candidate_sha256": sha}
    return None


def needed_incumbents(epoch: dict, *, grades: dict, scores: dict) -> dict:
    """Identify only checkpoints needed for a potential qualifying challenge."""
    roles = epoch.get("active_roles", {})
    origin = epoch["introduced_grade"]
    mastered = sum(v["correct"] == v["total"] for v in scores.values())
    needed = {}
    for grade in grades:
        caps = _grade_caps(grades, grade)
        if grade == origin:
            if not set(caps) <= set(scores):
                continue
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
                if cap in roles:
                    pointer = roles[cap]["checkpoint"]
                    needed[pointer["sha256"]] = pointer
    return needed


def _external_takeovers(grades, origin, scores, pointer, roles,
                        challenger_exam, incumbent_exams, record):
    decisions = []
    for grade in grades:
        if grade == origin:
            continue
        caps = _grade_caps(grades, grade)
        blocked = _incomplete_grade_decision(
            grade, caps, scores, pointer["sha256"], origin=False)
        if blocked:
            decisions.append(blocked)
            continue
        owners = {cap: roles[cap]["checkpoint"]["sha256"]
                  for cap in caps if cap in roles}
        verdict = cross_origin_takeover(
            grade_capabilities=caps, admitted_capabilities=tuple(scores),
            active_role_owners=owners, challenger_exam=challenger_exam,
            incumbent_exams={sha: incumbent_exams[sha] for sha in set(owners.values())})
        decisions.append({"grade": grade, **verdict})
        if verdict["decision"] in ("ELIGIBLE", "ELIGIBLE_UNCONTESTED_GRADE"):
            for cap in caps:
                record(cap)
    return decisions


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
    if pointer["optimizer_step"] <= epoch.get("championship_eligibility_after_step", -1):
        return updated, (), ()

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
    current_grade = _grade_caps(grades, origin)
    own_blocker = _incomplete_grade_decision(
        origin, current_grade, scores, pointer["sha256"], origin=True)
    if own_blocker:
        decisions.append(own_blocker)
    # Even an individual same-origin title is not awarded from a partially
    # tested checkpoint. Unintroduced or unscored peers mean no promotion yet.
    for cap in current_grade if own_blocker is None else ():
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

    # Foreign-grade promotion is atomic: record only a complete all-perfect
    # grade after any actual displaced owners have lost the school comparison.
    decisions.extend(_external_takeovers(
        grades, origin, scores, pointer, roles,
        challenger_exam, incumbent_exams, record))
    return updated, tuple(changes), tuple(decisions)
