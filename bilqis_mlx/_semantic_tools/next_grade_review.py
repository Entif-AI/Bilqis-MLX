"""Read-only, repeatable evidence inventory for each proposed next grade.

This checks structure, provenance slots and prerequisite order. A green report
cannot independently prove semantic truth or authorize a neural run.
"""
from __future__ import annotations

from .paths import REPO_ROOT

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

from .verification.review_evidence import EvidenceContext, EvidenceInventory

SCHEMA = "bilqis.next-grade-review/v3"
AUTHORITY = "IPR-0220/grade-questions-20261017"
QUESTION_IDS = tuple(f"Q{i:02d}" for i in range(1, 11))
PHASES = ("selection", "construction", "admission", "operation", "retrospective")
REVIEW_ROOT = REPO_ROOT / "docs" / "provenance" / "grade-reviews"
TEXT_RELEVANCE = frozenset(("DIRECT_TEXT_SEMANTIC_TRANSFER",
                            "TEXT_SURFACE_CONSTRAINT_FOR_COMPOSITION"))
DECISION_FIELDS = ("why_now", "why_not_alternatives", "what_changed_since_last_grade",
                   "expected_near_term_transfer", "smallest_staircase_step")
INITIAL_FUNCTION_FAMILIES = ("association", "disambiguation", "identification")
FUNCTION_POSTURES = frozenset(("DEFERRED", "FOUNDATIONAL",
                             "REQUIRES_QUALIFIED_IMPLEMENTATION"))


def subject_digest(record: dict, phase: str = "selection") -> str:
    """Changing the grade decision or its dependencies invalidates older reviews."""
    body = {key: record.get(key) for key in (
        "schema", "authority", "grade", "parent_release", "modality", "selected",
        "candidates", "decision", "semantic_function_families", "semantic_release")}
    if phase == "retrospective":
        body["run_outcome"] = record.get("run_outcome")
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _substantive(value):
    return isinstance(value, str) and bool(value.strip()) and value.strip().upper() not in {
        "TBD", "TODO", "UNKNOWN", "NONE", "N/A", "PENDING"}


def _identity(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:/-]*", value) is not None


def _report(grade, phase, problems, *, selected=None, reviewed=()):
    return {"schema": SCHEMA, "authority": AUTHORITY, "grade": grade,
            "phase": phase, "status": ("BLOCKED" if problems else
                                         "READY_FOR_INDEPENDENT_REVIEW"),
            "blockers": list(dict.fromkeys(problems)),
            "selected_candidate": selected, "question_ids": list(QUESTION_IDS),
            "reviewed_phases": list(reviewed),
            "training_authorized_by_this_report": False}


def configured_evidence() -> EvidenceContext | None:
    """Operator/reviewer configuration lives outside the candidate dossier."""
    manifest = os.environ.get("BILQIS_REVIEW_EVIDENCE_MANIFEST")
    if not manifest:
        return None
    return EvidenceContext(Path(manifest),
                           os.environ.get("BILQIS_EXPECTED_REVIEW_EVIDENCE_SHA256"),
                           REVIEW_ROOT.parents[1])


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


def evidence_references(record: dict, phase: str) -> list:
    """Collect only dependencies consumed by this phase's review."""
    candidates = record.get("candidates")
    chosen = next((c for c in candidates if isinstance(c, dict) and
                   c.get("id") == record.get("selected")), {}) if isinstance(candidates, list) else {}
    references = [c.get("source") for c in candidates if isinstance(c, dict)] if isinstance(candidates, list) else []
    prerequisites = chosen.get("prerequisites")
    if isinstance(prerequisites, list):
        references.extend(p.get("evidence") for p in prerequisites if isinstance(p, dict))
    reviews = record.get("reviews")
    answers = reviews.get(phase) if isinstance(reviews, dict) else None
    if isinstance(answers, dict):
        for q in QUESTION_IDS:
            answer = answers.get(q)
            if isinstance(answer, dict) and isinstance(answer.get("evidence"), list):
                references.extend(answer["evidence"])
    if phase == "retrospective" and isinstance(record.get("run_outcome"), dict):
        references.append(record["run_outcome"].get("evidence"))
    return references


def assess(record: dict, *, grade: str, parent_release: str,
           phase: str = "selection", evidence: EvidenceContext | None = None) -> dict:
    """Check all ten questions on every phase through the requested phase."""
    if phase not in PHASES or not isinstance(grade, str) or not re.fullmatch(r"[A-Z]+", grade):
        raise ValueError("NEXT_GRADE_REVIEW_INVALID_REQUEST")
    errors = []
    if not isinstance(record, dict) or record.get("schema") != SCHEMA or record.get("authority") != AUTHORITY:
        return _report(grade, phase, ["NEXT_GRADE_REVIEW_SCHEMA_OR_AUTHORITY_DRIFT"])
    if record.get("grade") != grade:
        errors.append("NEXT_GRADE_REVIEW_GRADE_MISMATCH")
    if not _substantive(parent_release):
        errors.append("NEXT_GRADE_REVIEW_PARENT_REQUIRED")
    if record.get("parent_release") != parent_release:
        errors.append("NEXT_GRADE_REVIEW_STALE_PARENT")
    if record.get("modality") != "TEXT_ONLY":
        errors.append("LEARNER_MODALITY_UNVERIFIED")
    if not _substantive(record.get("semantic_release")):
        errors.append("NEXT_GRADE_SEMANTIC_RELEASE_REQUIRED")
    inventory = (evidence.inspect(grade=grade, parent_release=parent_release,
                 semantic_release=record.get("semantic_release"),
                 subject_sha256=subject_digest(record)) if evidence else
                 EvidenceInventory({}, ("REVIEW_EVIDENCE_TRUST_ROOT_MISSING",)))
    errors.extend(inventory.blockers)

    candidates = record.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 2:
        errors.append("GRADE_ALTERNATIVE_COMPARISON_MISSING")
        candidates = []
    ids = [c.get("id") for c in candidates if isinstance(c, dict)]
    if (len(ids) != len(candidates) or any(not _identity(x) for x in ids)
            or len(set(ids)) != len(ids)):
        errors.append("GRADE_CANDIDATE_IDENTITY_INVALID")
    for candidate in candidates:
        if isinstance(candidate, dict) and not inventory.supports(
                [candidate.get("source")], "candidate:" + str(candidate.get("id")) + ":source"):
            errors.append("GRADE_CANDIDATE_SOURCE_UNVERIFIED:" + str(candidate.get("id")))
    selected = record.get("selected")
    if not _substantive(selected):
        errors.append("NEXT_GRADE_NOT_SELECTED")
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
        if not inventory.supports([chosen.get("source")], "candidate:" + str(selected) + ":source"):
            errors.append("SELECTED_TOPIC_SOURCE_UNVERIFIED")
        if not _substantive(chosen.get("smallest_increment")):
            errors.append("SELECTED_TOPIC_COMPLEXITY_INCREMENT_MISSING")
        prereqs = chosen.get("prerequisites")
        if not isinstance(prereqs, list) or not prereqs:
            errors.append("SELECTED_TOPIC_PREREQUISITES_NOT_REVIEWED")
        else:
            prerequisite_ids = [p.get("id") for p in prereqs if isinstance(p, dict)]
            if (any(not _identity(identity) for identity in prerequisite_ids) or
                    len({identity for identity in prerequisite_ids if isinstance(identity, str)}) != len(prerequisite_ids)):
                errors.append("PREREQUISITE_IDENTITY_INVALID")
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
                elif not inventory.supports([p.get("evidence")],
                         "prerequisite:" + str(p.get("id")) + ":" + str(p.get("state"))):
                    errors.append("PREREQUISITE_EVIDENCE_UNVERIFIED:" + str(p.get("id")))
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
    reviewed, phase_digests = [], {}
    for reviewed_phase in PHASES[:PHASES.index(phase)+1]:
        references = evidence_references(record, reviewed_phase)
        errors.extend(inventory.problems_for(references))
        phase_reviews = reviews.get(reviewed_phase) if isinstance(reviews, dict) else None
        if not isinstance(phase_reviews, dict):
            errors.append("REVIEW_PHASE_MISSING:" + reviewed_phase)
            continue
        reviewed.append(reviewed_phase)
        if phase_reviews.get("subject_sha256") != subject_digest(record, reviewed_phase):
            errors.append("REVIEW_SCOPE_STALE:" + reviewed_phase)
        evidence_digest = inventory.digest_for(references)
        phase_digests[reviewed_phase] = evidence_digest
        if phase_reviews.get("evidence_sha256") != evidence_digest or not evidence_digest:
            errors.append("REVIEW_EVIDENCE_SCOPE_STALE:" + reviewed_phase)
        for q in QUESTION_IDS:
            answer = phase_reviews.get(q)
            if not isinstance(answer, dict):
                errors.append("REVIEW_QUESTION_MISSING:" + reviewed_phase + ":" + q)
            elif (answer.get("status") != "EVIDENCED" or
                  not isinstance(answer.get("evidence"), list) or
                  not inventory.supports(answer["evidence"], "review:" + reviewed_phase + ":" + q)):
                errors.append("REVIEW_QUESTION_UNRESOLVED:" + reviewed_phase + ":" + q)
    if phase == "retrospective":
        outcome = record.get("run_outcome")
        if not isinstance(outcome, dict) or not inventory.supports(
                [outcome.get("evidence")], "run_outcome:" + subject_digest(record, phase)):
            errors.append("REVIEW_RETROSPECTIVE_OUTCOME_UNVERIFIED")
    report = _report(grade, phase, errors, selected=selected, reviewed=reviewed)
    report.update(semantic_release=record.get("semantic_release"),
                  subject_sha256=subject_digest(record, phase),
                  evidence_manifest_sha256=inventory.manifest_sha256,
                  phase_evidence_sha256=phase_digests)
    return report


def load_review(grade: str, directory: Path = REVIEW_ROOT, *,
                parent_release: str | None = None, phase: str = "selection",
                evidence: EvidenceContext | None = None) -> dict:
    """Only a local versioned proposal is considered; no Sheet row is approval."""
    if phase not in PHASES or not isinstance(grade, str) or not re.fullmatch(r"[A-Z]+", grade):
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
    return assess(data, grade=grade, parent_release=parent_release, phase=phase,
                  evidence=evidence if evidence is not None else configured_evidence())


def require_admission_review(grade: str, parent_release: str, *,
                             evidence: EvidenceContext | None = None) -> dict:
    """A structural prerequisite for new runtime admissions, not approval itself.

    Versioned source/semantic and whole-student transition gates remain separate.
    Existing A/B training and previously admitted grades must remain resumable.
    """
    report = load_review(grade, parent_release=parent_release, phase="admission", evidence=evidence)
    if report["status"] != "READY_FOR_INDEPENDENT_REVIEW":
        raise ValueError("NEXT_GRADE_REVIEW_BLOCKED:" + grade + ":" +
                         ",".join(report["blockers"]))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--phase", choices=PHASES, default="selection")
    parser.add_argument("--parent-release")
    parser.add_argument("--evidence-manifest", type=Path,
                        default=os.environ.get("BILQIS_REVIEW_EVIDENCE_MANIFEST"))
    parser.add_argument("--expected-evidence-sha256",
                        default=os.environ.get("BILQIS_EXPECTED_REVIEW_EVIDENCE_SHA256"))
    parser.add_argument("--artifact-root", type=Path, default=REVIEW_ROOT.parents[1])
    args = parser.parse_args(argv)
    evidence = (EvidenceContext(args.evidence_manifest, args.expected_evidence_sha256,
                               args.artifact_root) if args.evidence_manifest else None)
    report = load_review(args.grade, parent_release=args.parent_release, phase=args.phase,
                         evidence=evidence)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "READY_FOR_INDEPENDENT_REVIEW" else 2


if __name__ == "__main__":
    raise SystemExit(main())
