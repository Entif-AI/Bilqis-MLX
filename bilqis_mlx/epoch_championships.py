"""Active best-score championship ownership within one curriculum epoch.

Historical champion and soup receipts stay in the old state fields. The
epoch owns fresh best-score winners and their frozen vote entitlements.
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


def rebase_active_championships(epoch: dict, *, prior_student: dict,
                                baseline: dict, generation: int) -> dict:
    """Replace an experiment's non-teaching baseline and clear earned authority.

    This is intentionally different from a routine idempotent reset: it is an
    explicit experiment rebase. The former active epoch remains archived. The
    replacement baseline is a non-teaching custody/reference checkpoint, not a
    fictitious incumbent that globally blocks later best-score capability roles.
    """
    prior = _pointer(prior_student)
    replacement = _pointer(baseline)
    previous_baseline = _pointer(epoch["baseline"])
    previous_graduate = epoch.get("previous_graduate")
    if previous_graduate is not None:
        previous_graduate = _pointer(previous_graduate)
        if replacement["optimizer_step"] < previous_graduate["optimizer_step"]:
            raise ValueError("CHAMPIONSHIP_REBASE_PREDATES_PREVIOUS_GRADUATE")
    if type(generation) is not int or generation < 1:
        raise ValueError("CHAMPIONSHIP_REBASE_INVALID_GENERATION")
    updated = deepcopy(epoch)
    archive = {
        "source_generation": generation,
        "starting_student": prior,
        "prior_baseline": previous_baseline,
        "active_roles": updated.get("active_roles", {}),
        "active_grade_soups": updated.get("active_grade_soups", {}),
        "qualified": updated.get("qualified", []),
        "baseline_roles": updated.get("baseline_roles", {}),
        "active_championship_reset": updated.get("active_championship_reset"),
    }
    updated["superseded_active_championships"] = [
        *updated.get("superseded_active_championships", []), archive]
    updated["baseline"] = replacement
    updated["active_roles"] = {}
    updated["active_grade_soups"] = {}
    updated["baseline_roles"] = {}
    updated["qualified"] = []
    updated["earned_role_votes_at_reset"] = 0
    updated["guidance_policy"] = EARNED_ONLY_POLICY
    updated["championship_eligibility_after_step"] = replacement["optimizer_step"]
    updated["baseline_challenge_required"] = False
    updated["baseline_surpassed"] = None
    updated["active_championship_reset"] = {
        "policy": EARNED_ONLY_POLICY,
        "source_generation": generation,
        "student_sha256": replacement["sha256"],
        "optimizer_step": replacement["optimizer_step"],
        "old_active_role_count": len(archive["active_roles"]),
        "old_active_soup_grades": sorted(archive["active_grade_soups"]),
        "preexisting_championships_archived": True,
        "training_or_optimizer_updates": 0,
        "experiment_baseline_rebased": True,
        "baseline_challenge_required": False,
    }
    return updated


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
    return None


def _role_matches_exam(role: dict, exam: dict) -> bool:
    return (
        role.get("cohort_sha256") == exam.get("cohort_sha256") and
        role.get("rubric") == exam.get("rubric_sha256") and
        role.get("assessment_scope_sha256") == exam.get("assessment_scope_sha256") and
        role.get("source_graph_sha256") == exam.get("source_graph_sha256") and
        role.get("source_oracle_sha256") == exam.get("source_oracle_sha256")
    )


def _exam_matches(challenger: dict, incumbent: dict) -> None:
    common = ("cohort_sha256", "rubric_sha256", "assessment_scope_sha256",
              "source_graph_sha256", "source_oracle_sha256")
    if (not isinstance(incumbent, dict) or
            any(incumbent.get(field) != challenger.get(field) for field in common) or
            set(incumbent.get("scores", {})) != set(challenger.get("scores", {})) or
            any(incumbent["scores"][cap].get("total") !=
                challenger["scores"][cap].get("total")
                for cap in challenger.get("scores", {}))):
        raise ValueError("CHAMPIONSHIP_EPOCH_SAME_COHORT_REQUIRED")


def needed_incumbents(epoch: dict, *, grades: dict,
                      challenger_exam: dict) -> dict:
    """Request only owners that lack enough bound evidence for this challenge."""
    roles = epoch.get("active_roles", {})
    origin = epoch["introduced_grade"]
    scores = challenger_exam["scores"]
    challenger = _pointer(challenger_exam["checkpoint"])
    needed = {}
    for grade in grades:
        caps = _grade_caps(grades, grade)
        if not set(caps) <= set(scores):
            continue
        grade_perfect = all(scores[cap]["correct"] == scores[cap]["total"]
                            for cap in caps)
        for cap in caps:
            prior = roles.get(cap)
            if prior is None:
                continue
            pointer = _pointer(prior["checkpoint"])
            if pointer["sha256"] == challenger["sha256"]:
                continue
            role_bound = _role_matches_exam(prior, challenger_exam)
            max_takeover = (grade != origin and grade_perfect and
                            prior.get("correct") == prior.get("total") and
                            scores[cap]["correct"] == scores[cap]["total"])
            if not role_bound or max_takeover:
                needed[pointer["sha256"]] = pointer
    return needed


def _incumbent_score(capability: str, prior: dict, challenger_exam: dict,
                     incumbent_exams: dict) -> tuple[dict, int]:
    prior_pointer = _pointer(prior["checkpoint"])
    if _role_matches_exam(prior, challenger_exam):
        return ({"correct": prior["correct"], "total": prior["total"]},
                prior.get("breadth", 0))
    incumbent = incumbent_exams.get(prior_pointer["sha256"])
    if incumbent is None:
        raise ValueError("CHAMPIONSHIP_EPOCH_INCUMBENT_EXAM_REQUIRED")
    _exam_matches(challenger_exam, incumbent)
    prior_score = incumbent["scores"][capability]
    prior_breadth = sum(
        value["correct"] == value["total"]
        for value in incumbent["scores"].values())
    return prior_score, prior_breadth


def _role_action(*, capability: str, grade: str, origin: str, roles: dict,
                 scores: dict, pointer: dict, breadth: int,
                 challenger_exam: dict, incumbent_exams: dict) -> tuple[str, str | None]:
    """Return RECORD, KEEP, or MAX_TIE for one completely scored capability."""
    prior = roles.get(capability)
    if prior is None:
        return "RECORD", None
    prior_pointer = _pointer(prior["checkpoint"])
    if prior_pointer["sha256"] == pointer["sha256"]:
        return "KEEP", None
    previous, incumbent_breadth = _incumbent_score(
        capability, prior, challenger_exam, incumbent_exams)
    candidate = scores[capability]
    if candidate["total"] != previous["total"]:
        raise ValueError("CHAMPIONSHIP_EPOCH_SCORE_TOTAL_DRIFT")
    if candidate["correct"] > previous["correct"]:
        return "RECORD", None
    equal_max = (candidate["correct"] == previous["correct"] ==
                 candidate["total"])
    if not equal_max:
        return "KEEP", None
    if grade == origin:
        return ("RECORD", None) if breadth > incumbent_breadth else ("KEEP", None)
    return "MAX_TIE", prior_pointer["sha256"]


def _role_receipt(challenger_exam: dict, capability: str,
                  mastered: tuple[str, ...]) -> dict:
    pointer = challenger_exam["checkpoint"]
    score = challenger_exam["scores"][capability]
    return {
        "rubric": challenger_exam["rubric_sha256"],
        "capability": capability,
        "cohort_sha256": challenger_exam["cohort_sha256"],
        "assessment_scope_sha256": challenger_exam["assessment_scope_sha256"],
        "source_graph_sha256": challenger_exam["source_graph_sha256"],
        "source_oracle_sha256": challenger_exam["source_oracle_sha256"],
        "correct": score["correct"], "total": score["total"],
        "breadth": len(mastered), "perfect_capabilities": list(mastered),
        "checkpoint": dict(pointer),
        "evaluation_id": ("championship-epoch/" + challenger_exam["cohort_sha256"] +
                          "/" + pointer["sha256"]),
    }


def _max_takeover_decision(grade: str, owners: dict, grades: dict,
                           challenger_exam: dict, incumbent_exams: dict) -> dict | None:
    caps = _grade_caps(grades, grade)
    scores = challenger_exam["scores"]
    if not all(scores[cap]["correct"] == scores[cap]["total"] for cap in caps):
        return None
    required = {sha: incumbent_exams[sha] for sha in set(owners.values())}
    verdict = cross_origin_takeover(
        grade_capabilities=caps, admitted_capabilities=tuple(scores),
        active_role_owners=owners, challenger_exam=challenger_exam,
        incumbent_exams=required)
    return {"grade": grade, **verdict}


def advance_epoch(epoch: dict, *, grades: dict, challenger_exam: dict,
                  incumbent_exams: dict) -> tuple[dict, tuple[str, ...], tuple[dict, ...]]:
    """Advance best-score roles; tighten replacement only at a score ceiling."""
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
    # Empty roles accept the first complete-grade measurement. Non-max roles
    # are ordinary best-score competitions: only a strict capability gain
    # displaces the incumbent. Ties preserve the incumbent.
    cross_origin_max_owners = {}
    for grade in grades:
        caps = _grade_caps(grades, grade)
        blocker = _incomplete_grade_decision(
            grade, caps, scores, pointer["sha256"], origin=(grade == origin))
        if blocker:
            decisions.append(blocker)
            continue
        max_owners = {}
        for cap in caps:
            action, owner = _role_action(
                capability=cap, grade=grade, origin=origin, roles=roles,
                scores=scores, pointer=pointer, breadth=breadth,
                challenger_exam=challenger_exam, incumbent_exams=incumbent_exams)
            if action == "RECORD":
                roles[cap] = _role_receipt(challenger_exam, cap, mastered)
                changes.append(cap)
            elif action == "MAX_TIE":
                max_owners[cap] = owner
        if max_owners:
            cross_origin_max_owners[grade] = max_owners

    # Once a capability is already at its maximum, another equal-max score is
    # no longer a numerical improvement. Cross-origin replacement therefore
    # falls back to the stronger existing full-grade + strict-school rule for
    # only those maxed incumbent roles. Non-max gains above have already moved.
    for grade, owners in cross_origin_max_owners.items():
        verdict = _max_takeover_decision(
            grade, owners, grades, challenger_exam, incumbent_exams)
        if verdict is None:
            continue
        decisions.append(verdict)
        if verdict["decision"] == "ELIGIBLE":
            for cap in owners:
                roles[cap] = _role_receipt(challenger_exam, cap, mastered)
                if cap not in changes:
                    changes.append(cap)
    return updated, tuple(changes), tuple(decisions)
