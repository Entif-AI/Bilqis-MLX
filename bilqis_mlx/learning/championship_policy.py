"""Source-bound, neural-inert cross-origin grade championship eligibility.

This module decides eligibility, not checkpoint ownership or soup materialization.
See docs/specifications/0002_CHAMPIONSHIP_LIFECYCLE_V1.md.
"""
from __future__ import annotations


SCHEMA = "bilqis.mlx.cross-origin-championship/v1"
CONTEXT_KEYS = (
    "cohort_sha256", "rubric_sha256", "assessment_scope_sha256",
    "source_graph_sha256", "source_oracle_sha256",
)


def _sha(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(char in "0123456789abcdef" for char in value))


def _exam(exam, admitted, *, allow_grade_only=False, grade=()):
    if (not isinstance(exam, dict) or
            any(not _sha(exam.get(key)) for key in CONTEXT_KEYS)):
        raise ValueError("CHAMPIONSHIP_INCOMPARABLE_EXAM_CONTEXT")
    pointer = exam.get("checkpoint")
    if (not isinstance(pointer, dict) or not _sha(pointer.get("sha256")) or
            not isinstance(pointer.get("filename"), str) or
            not pointer["filename"].startswith("bundles/") or
            type(pointer.get("optimizer_step")) is not int or
            pointer["optimizer_step"] < 0 or
            pointer.get("model_and_native_adamw") is not True):
        raise ValueError("CHAMPIONSHIP_WHOLE_STUDENT_OWN_ADAMW_REQUIRED")
    scores = exam.get("scores")
    if (not isinstance(scores, dict) or
            (not allow_grade_only and set(scores) != admitted) or
            (allow_grade_only and
             (not set(grade) <= set(scores) or not set(scores) <= admitted))):
        raise ValueError("CHAMPIONSHIP_INCOMPLETE_CUMULATIVE_SCHOOL")
    correct = total = 0
    for score in scores.values():
        if (not isinstance(score, dict) or
                type(score.get("correct")) is not int or
                type(score.get("total")) is not int or
                not 0 <= score["correct"] <= score["total"] or
                score["total"] < 1):
            raise ValueError("CHAMPIONSHIP_INVALID_SOURCE_SCORES")
        correct += score["correct"]
        total += score["total"]
    return correct, total


def cross_origin_takeover(*, grade_capabilities, admitted_capabilities,
                          active_role_owners, challenger_exam,
                          incumbent_exams):
    """Decide full-grade takeover only after same-cohort whole-school proof.

    A role owner maps capability -> whole checkpoint SHA. Every distinct
    incumbent must be independently re-examined on the same complete cohort.
    Invalid or absent proof fails closed; a score tie never displaces a role.
    """
    grade = tuple(grade_capabilities)
    school = tuple(admitted_capabilities)
    required, admitted = set(grade), set(school)
    if (not required or not admitted or
            len(grade) != len(required) or len(school) != len(admitted) or
            any(not isinstance(cap, str) or not cap for cap in school) or
            not required <= admitted or
            not isinstance(active_role_owners, dict) or
            not set(active_role_owners) <= required or
            any(not _sha(sha) for sha in active_role_owners.values()) or
            not isinstance(incumbent_exams, dict) or
            set(incumbent_exams) != set(active_role_owners.values())):
        raise ValueError("CHAMPIONSHIP_INCOMPLETE_TARGET_GRADE_OR_INCUMBENTS")

    # An uncontested title needs complete evidence only for the destination
    # grade. Whole-school incumbent comparisons are required exclusively when
    # actual championship owners would be displaced.
    uncontested = not active_role_owners
    challenger_correct, challenger_total = _exam(
        challenger_exam, admitted, allow_grade_only=uncontested, grade=required)
    complete_school = set(challenger_exam["scores"]) == admitted
    contender = challenger_exam["checkpoint"]["sha256"]
    comparisons = []
    for sha, exam in sorted(incumbent_exams.items()):
        before_correct, before_total = _exam(exam, admitted)
        if (sha != exam["checkpoint"]["sha256"] or
                any(exam[key] != challenger_exam[key] for key in CONTEXT_KEYS) or
                any(exam["scores"][cap]["total"] !=
                    challenger_exam["scores"][cap]["total"] for cap in admitted) or
                before_total != challenger_total):
            raise ValueError("CHAMPIONSHIP_INCOMPARABLE_CUMULATIVE_COHORT")
        comparisons.append({"incumbent_sha256": sha,
                            "correct": before_correct, "total": before_total})

    grade_perfect = all(challenger_exam["scores"][cap]["correct"] ==
                        challenger_exam["scores"][cap]["total"]
                        for cap in required)
    if not grade_perfect:
        decision = "DENY_TARGET_GRADE_NOT_PERFECT"
    elif not comparisons:
        decision = "ELIGIBLE_UNCONTESTED_GRADE"
    elif contender in incumbent_exams:
        decision = "DENY_EXISTING_OWNER"
    elif any(challenger_correct <= row["correct"] for row in comparisons):
        decision = "DENY_NO_STRICT_SCHOOL_VICTORY"
    else:
        decision = "ELIGIBLE"
    return {
        "schema": SCHEMA, "decision": decision,
        "target_capabilities": list(grade),
        "school_correct": challenger_correct if complete_school else None,
        "school_total": challenger_total if complete_school else None,
        "challenger_sha256": contender,
        "incumbents": comparisons,
        "cohort_sha256": challenger_exam["cohort_sha256"],
        "rubric_sha256": challenger_exam["rubric_sha256"],
        "assessment_scope_sha256": challenger_exam["assessment_scope_sha256"],
        "source_graph_sha256": challenger_exam["source_graph_sha256"],
        "source_oracle_sha256": challenger_exam["source_oracle_sha256"],
    }
