"""Read-only, repeatable evidence inventory for each proposed next grade.

This checks structure, provenance slots and prerequisite order. A green report
cannot independently prove semantic truth or authorize a neural run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "bilqis.next-grade-review/v2"
AUTHORITY = "IPR-0220/grade-questions-20261017"
QUESTION_IDS = tuple(f"Q{i:02d}" for i in range(1, 11))
PHASES = ("selection", "construction", "admission", "operation", "retrospective")
REVIEW_ROOT = Path(__file__).resolve().parents[1] / "docs" / "grade-reviews"
TEXT_RELEVANCE = frozenset(("DIRECT_TEXT_SEMANTIC_TRANSFER",
                            "TEXT_SURFACE_CONSTRAINT_FOR_COMPOSITION"))
DECISION_FIELDS = ("why_now", "why_not_alternatives", "what_changed_since_last_grade",
                   "expected_near_term_transfer", "smallest_staircase_step")
INITIAL_FUNCTION_FAMILIES = ("association", "disambiguation", "identification")
FUNCTION_POSTURES = frozenset(("DEFERRED", "FOUNDATIONAL",
                             "REQUIRES_QUALIFIED_IMPLEMENTATION"))


def subject_digest(record: dict) -> str:
    """Changing the grade decision or its dependencies invalidates older reviews."""
    body = {key: record.get(key) for key in (
        "schema", "authority", "grade", "parent_release", "modality", "selected",
        "candidates", "decision", "semantic_function_families", "run_outcome")}
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _substantive(value):
    return isinstance(value, str) and bool(value.strip()) and value.strip().upper() not in {
        "TBD", "TODO", "UNKNOWN", "NONE", "N/A", "PENDING"}


def _report(grade, phase, problems, *, selected=None, reviewed=()):
    return {"schema": SCHEMA, "authority": AUTHORITY, "grade": grade,
            "phase": phase, "status": ("BLOCKED" if problems else
                                         "READY_FOR_INDEPENDENT_REVIEW"),
            "blockers": list(dict.fromkeys(problems)),
            "selected_candidate": selected, "question_ids": list(QUESTION_IDS),
            "reviewed_phases": list(reviewed),
            "training_authorized_by_this_report": False}


def _check_semantic_function_plan(record: dict, errors: list[str]) -> None:
    """Require forward-looking decisions, never pretend contextual code exists.

    Initial families are a minimum review inventory, not an exhaustive ontology.
    DEFERRED and FOUNDATIONAL make no implementation/mastery assertions.
    """
    plan = record.get("semantic_function_families")
    if not isinstance(plan, dict):
        plan = {}
    for family in INITIAL_FUNCTION_FAMILIES:
        if family not in plan:
            errors.append("SEMANTIC_FUNCTION_NOT_CONSIDERED:" + family)
    for family, item in plan.items():
        if not isinstance(family, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", family):
            errors.append("SEMANTIC_FUNCTION_FAMILY_INVALID")
            continue
        posture = item.get("posture") if isinstance(item, dict) else None
        if not isinstance(posture, str) or posture not in FUNCTION_POSTURES:
            errors.append("SEMANTIC_FUNCTION_POSTURE_INVALID:" + family)
            continue
        if not _substantive(item.get("rationale")):
            errors.append("SEMANTIC_FUNCTION_RATIONALE_MISSING:" + family)
        if item["posture"] == "REQUIRES_QUALIFIED_IMPLEMENTATION":
            # No string in a grade dossier can qualify a future interpreter.
            errors.append("SEMANTIC_FUNCTION_QUALIFICATION_REQUIRED:" + family)


def assess(record: dict, *, grade: str, parent_release: str,
           phase: str = "selection") -> dict:
    """Check all ten questions on every phase through the requested phase."""
    if phase not in PHASES or not isinstance(grade, str) or not re.fullmatch(r"[A-Z]", grade):
        raise ValueError("NEXT_GRADE_REVIEW_INVALID_REQUEST")
    errors = []
    if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("authority") != AUTHORITY:
        return _report(grade, phase, ["NEXT_GRADE_REVIEW_SCHEMA_OR_AUTHORITY_DRIFT"])
    if record.get("grade") != grade:
        errors.append("NEXT_GRADE_REVIEW_GRADE_MISMATCH")
    if record.get("parent_release") != parent_release:
        errors.append("NEXT_GRADE_REVIEW_STALE_PARENT")
    if record.get("modality") != "TEXT_ONLY":
        errors.append("LEARNER_MODALITY_UNVERIFIED")

    candidates = record.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 2:
        errors.append("GRADE_ALTERNATIVE_COMPARISON_MISSING")
        candidates = []
    ids = [c.get("id") for c in candidates if isinstance(c, dict)]
    if (len(ids) != len(candidates) or any(not _substantive(x) for x in ids)
            or len(set(ids)) != len(ids)):
        errors.append("GRADE_CANDIDATE_IDENTITY_INVALID")
    selected = record.get("selected")
    chosen = next((c for c in candidates if isinstance(c, dict) and
                   c.get("id") == selected), None)
    if chosen is None:
        errors.append("NEXT_GRADE_NOT_SELECTED")
    else:
        # The Sheet is allowed to nominate candidates but cannot certify its
        # own claims. Text benefits, independent sources and alternatives matter.
        relevance = chosen.get("text_model_relevance")
        if (not isinstance(relevance, str) or relevance not in TEXT_RELEVANCE or
                not _substantive(chosen.get("needs_neural_learning"))):
            errors.append("SELECTED_TOPIC_TEXT_RELEVANCE_UNPROVEN")
        if not _substantive(chosen.get("source")) or chosen["source"].startswith("sheet:"):
            errors.append("SELECTED_TOPIC_SOURCE_NOT_INDEPENDENT")
        if not _substantive(chosen.get("smallest_increment")):
            errors.append("SELECTED_TOPIC_COMPLEXITY_INCREMENT_MISSING")
        prereqs = chosen.get("prerequisites")
        if not isinstance(prereqs, list) or not prereqs:
            errors.append("SELECTED_TOPIC_PREREQUISITES_NOT_REVIEWED")
        else:
            for p in prereqs:
                if not isinstance(p, dict):
                    errors.append("PREREQUISITE_MALFORMED")
                    continue
                ok = (p.get("state") == "MASTERED" and _substantive(p.get("evidence")))
                if p.get("state") == "EARLIER_STAGE":
                    stage, dependent = p.get("stage"), p.get("dependent_stage")
                    ok = (type(stage) is int and type(dependent) is int and
                          0 <= stage < dependent and _substantive(p.get("evidence")))
                if not ok:
                    errors.append("PREREQUISITE_NOT_DISCHARGED:" + str(p.get("id", "UNKNOWN")))
        unlocks = chosen.get("unlocks")
        if (not isinstance(unlocks, list) or not unlocks or
                any(not isinstance(u, dict) or not _substantive(u.get("capability")) or
                    u.get("via") != selected or not _substantive(u.get("why")) for u in unlocks)):
            errors.append("SELECTED_TOPIC_UNLOCKS_NOT_TRACEABLE")
        foundations = chosen.get("frontloaded_foundations")
        if not isinstance(foundations, list):
            errors.append("FUTURE_FOUNDATION_FRONTLOAD_NOT_EVALUATED")
        elif any(not isinstance(f, dict) or not _substantive(f.get("id")) or
                 not _substantive(f.get("unblocks")) or not _substantive(f.get("timing"))
                 for f in foundations):
            errors.append("FUTURE_FOUNDATION_FRONTLOAD_NOT_JUSTIFIED")

    decision = record.get("decision") or {}
    if not isinstance(decision, dict):
        decision = {}
    for key in DECISION_FIELDS:
        value = decision.get(key)
        if key == "why_not_alternatives":
            expected = {name for name in ids if isinstance(name, str) and name != selected}
            if not isinstance(value, dict) or set(value) != expected or not all(
                    _substantive(v) for v in value.values()):
                errors.append("GRADE_COMPARISON_ALTERNATIVES_NOT_JUSTIFIED")
        elif not _substantive(value):
            errors.append("GRADE_DECISION_REASON_MISSING:" + key)

    _check_semantic_function_plan(record, errors)

    reviews = record.get("reviews") or {}
    reviewed = []
    current_digest = subject_digest(record)
    for reviewed_phase in PHASES[:PHASES.index(phase)+1]:
        phase_reviews = reviews.get(reviewed_phase) if isinstance(reviews, dict) else None
        if not isinstance(phase_reviews, dict):
            errors.append("REVIEW_PHASE_MISSING:" + reviewed_phase)
            continue
        reviewed.append(reviewed_phase)
        if phase_reviews.get("subject_sha256") != current_digest:
            errors.append("REVIEW_SCOPE_STALE:" + reviewed_phase)
        for q in QUESTION_IDS:
            answer = phase_reviews.get(q)
            if not isinstance(answer, dict):
                errors.append("REVIEW_QUESTION_MISSING:" + reviewed_phase + ":" + q)
            elif (answer.get("status") != "EVIDENCED" or
                  not isinstance(answer.get("evidence"), list) or
                  not answer["evidence"] or not all(
                      _substantive(x) and x.startswith(("repo:", "run:", "issue:",
                                                          "source:", "https://"))
                      for x in answer["evidence"])):
                errors.append("REVIEW_QUESTION_UNRESOLVED:" + reviewed_phase + ":" + q)
    if phase == "retrospective" and not isinstance(record.get("run_outcome"), dict):
        errors.append("REVIEW_RETROSPECTIVE_OUTCOME_UNVERIFIED")
    return _report(grade, phase, errors, selected=selected, reviewed=reviewed)


def load_review(grade: str, directory: Path = REVIEW_ROOT, *,
                parent_release: str | None = None, phase: str = "selection") -> dict:
    """Only a local versioned proposal is considered; no Sheet row is approval."""
    if not isinstance(grade, str) or not re.fullmatch(r"[A-Z]", grade):
        raise ValueError("NEXT_GRADE_REVIEW_INVALID_GRADE")
    path = Path(directory) / (grade + ".json")
    if path.is_symlink():
        return _report(grade, phase, ["NEXT_GRADE_REVIEW_UNSAFE_PATH"])
    if not path.is_file():
        return _report(grade, phase, ["NEXT_GRADE_REVIEW_MISSING"])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return _report(grade, phase, ["NEXT_GRADE_REVIEW_UNREADABLE"])
    return assess(data, grade=grade, parent_release=(parent_release if parent_release is not None
                                                   else data.get("parent_release")), phase=phase)


def require_admission_review(grade: str, parent_release: str) -> dict:
    """A structural prerequisite for new runtime admissions, not approval itself.

    Versioned source/semantic and whole-student transition gates remain separate.
    Existing A/B training and previously admitted grades must remain resumable.
    """
    report = load_review(grade, parent_release=parent_release, phase="admission")
    if report["status"] != "READY_FOR_INDEPENDENT_REVIEW":
        raise ValueError("NEXT_GRADE_REVIEW_BLOCKED:" + grade + ":" +
                         ",".join(report["blockers"]))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--phase", choices=PHASES, default="selection")
    parser.add_argument("--parent-release")
    args = parser.parse_args(argv)
    report = load_review(args.grade, parent_release=args.parent_release, phase=args.phase)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "READY_FOR_INDEPENDENT_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
